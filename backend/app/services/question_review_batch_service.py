"""手动批量 AI 审核服务（补充开发文档 §5/§6/§7/§8）。

设计原则：
- 审核执行全部复用 QuestionReviewService（准入/去重门/决策复核/状态流转/指纹保护
  均在单题服务内，本服务不复制任何审核实现，不接触 Prompt/阈值/判定语义）；
- 同一题目同时仅一个"有效执行中"审核项：DB 唯一约束
  uq_qrbi_question_claim(question_id, claim_key)（claim_key='active' 活跃期间占用，
  终态后置 NULL；MySQL 唯一索引允许多 NULL），不依赖进程锁；
- item 状态与批次统计一致性：统计全部由 BatchItem 重算派生（§8 口径），幂等；
- 服务重启恢复（§8）：queued/running 批次可明确恢复——卡死项标记
  interrupted_by_restart 并释放认领，管理员可重新发起新批次（不无限重试）。
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from agent.common.config import agent_settings
from app.models.question import Question
from app.models.question_review_batch import QuestionReviewBatch, QuestionReviewBatchItem
from app.models.question_review_record import QuestionReviewRecord
from app.services.question_review_service import (
    FAIL_EXECUTION,
    SKIP_CONCURRENT_REVIEW,
    SKIP_QUESTION_NOT_PENDING,
    SKIP_UNSUPPORTED_TYPE,
    SKIP_DEDUP_DUPLICATE,
    SKIP_DEDUP_UNRESOLVED,
    QuestionReviewService,
)

logger = logging.getLogger("app.services.question_review_batch")

# 批次/批次项状态（§5）
BATCH_ACTIVE_STATUSES = ("queued", "running")
BATCH_TERMINAL_STATUSES = ("completed", "partial", "failed", "cancelled")
ITEM_ACTIVE_STATUSES = ("queued", "running")
ITEM_TERMINAL_STATUSES = ("completed", "failed", "skipped")

# 跳过原因码 → 可读说明（§6.1/§6.2 reason 必须可读）
REASON_TEXTS = {
    "question_not_found": "题目不存在",
    SKIP_QUESTION_NOT_PENDING: "题目状态不是待审核（已发布/已驳回/人工终态）",
    SKIP_UNSUPPORTED_TYPE: "题型不在自动审核范围（简答题等转人工）",
    SKIP_DEDUP_UNRESOLVED: "存在待人工复核的去重疑点，禁止自动审核",
    SKIP_DEDUP_DUPLICATE: "去重判定为重复题，禁止自动审核",
    SKIP_CONCURRENT_REVIEW: "该题已在其他批量审核任务中执行",
}

INTERRUPTED_CODE = "interrupted_by_restart"

CLAIM_KEY_ACTIVE = "active"


def _reason_text(code: str) -> str:
    return REASON_TEXTS.get(code, code)


def _now():
    return datetime.utcnow()


class QuestionReviewBatchService:
    """手动批量 AI 审核服务。"""

    def __init__(self, db: Session, *, review_agent=None) -> None:
        self.db = db
        self._review_service = QuestionReviewService(db, agent=review_agent)

    # ------------------------------------------------------------------
    # 预检（§6.1）：不建任务、不调 LLM、不产生持久化
    # ------------------------------------------------------------------
    def preview(self, question_ids: List[int]) -> Dict[str, Any]:
        ids = list(dict.fromkeys(question_ids or []))
        items: List[Dict[str, Any]] = []
        eligible_ids: List[int] = []
        for qid in ids:
            eligible, code = self._check_one(qid)
            items.append(
                {
                    "question_id": qid,
                    "eligible": eligible,
                    "reason_code": code if not eligible else "",
                    "reason": "" if eligible else _reason_text(code),
                }
            )
            if eligible:
                eligible_ids.append(qid)
        return {
            "requested": len(ids),
            "eligible": len(eligible_ids),
            "ineligible": len(ids) - len(eligible_ids),
            "eligible_question_ids": eligible_ids,
            "items": items,
        }

    # ------------------------------------------------------------------
    # 创建批次（§6.2）：重建校验 + DB 条件认领，快速返回
    # ------------------------------------------------------------------
    def create_batch(self, question_ids: List[int], created_by: int) -> Dict[str, Any]:
        ids = list(dict.fromkeys(question_ids or []))
        batch = QuestionReviewBatch(
            created_by=created_by,
            status="queued",
            total_count=len(ids),
            accepted_count=0,
            processed_count=0,
            auto_approved_count=0,
            auto_rejected_count=0,
            manual_review_count=0,
            failed_count=0,
            skipped_count=0,
            pending_count=0,
        )
        self.db.add(batch)
        self.db.flush()  # 拿到 batch.id

        accepted = 0
        for qid in ids:
            # 创建时必须重新校验（§6.2 不信任预检结果/前端）
            eligible, code = self._check_one(qid)
            if eligible:
                item = QuestionReviewBatchItem(
                    batch_id=batch.id,
                    question_id=qid,
                    status="queued",
                    claim_key=CLAIM_KEY_ACTIVE,
                )
                try:
                    with self.db.begin_nested():
                        self.db.add(item)
                        self.db.flush()  # 触发 uq_qrbi_question_claim 唯一约束
                    accepted += 1
                    continue
                except IntegrityError:
                    # 同题已有活动审核项（§5.2 重复提交不建活动项，DB 约束而非进程锁）。
                    # savepoint 已回滚失败的插入；须把失败实例从会话移除，
                    # 否则它滞留在 new 集，后续 flush 会重复触发同一冲突
                    try:
                        self.db.expunge(item)
                    except Exception:  # noqa: BLE001
                        pass
                    code = SKIP_CONCURRENT_REVIEW
            self.db.add(
                QuestionReviewBatchItem(
                    batch_id=batch.id,
                    question_id=qid,
                    status="skipped",
                    claim_key=None,
                    skip_reason=code,
                )
            )

        batch.accepted_count = accepted

        # §6 设计决策①：无任何可执行题目 → 不创建批次（业务错误由 API 层抛出）
        if accepted == 0:
            self.db.rollback()
            return {"error": "no_eligible_questions", "requested": len(ids), "accepted": 0, "skipped": len(ids)}

        self._recompute_stats(batch)
        self.db.commit()
        self.db.refresh(batch)
        return {
            "batch_id": batch.id,
            "status": batch.status,
            "requested": len(ids),
            "accepted": accepted,
            "skipped": len(ids) - accepted,
        }

    # ------------------------------------------------------------------
    # 后台执行（§7）：复用单题服务，独立会话，串行（MAX_CONCURRENCY 为上限）
    # ------------------------------------------------------------------
    def execute(self, batch_id: int) -> Dict[str, Any]:
        batch = self._get_batch(batch_id)
        if not batch:
            return {"batch_id": batch_id, "error": "batch_not_found"}
        if batch.status not in BATCH_ACTIVE_STATUSES:
            # 幂等：终态批次不重复执行
            return {"batch_id": batch_id, "status": batch.status, "stats": self._stats_dict(batch)}

        batch.status = "running"
        batch.started_at = batch.started_at or _now()
        self.db.commit()

        items = (
            self.db.query(QuestionReviewBatchItem)
            .filter(
                QuestionReviewBatchItem.batch_id == batch_id,
                QuestionReviewBatchItem.status == "queued",
                QuestionReviewBatchItem.claim_key == CLAIM_KEY_ACTIVE,
            )
            .order_by(QuestionReviewBatchItem.id)
            .all()
        )

        for item in items:
            item.status = "running"
            item.started_at = _now()
            self.db.commit()
            try:
                self._execute_item(item)
            except Exception as exc:  # noqa: BLE001 单题失败不影响其余（§8）
                logger.error(f"批量审核批次 {batch_id} 题目 {item.question_id} 执行异常: {exc}", exc_info=True)
                self.db.rollback()
                item.status = "failed"
                item.error_code = FAIL_EXECUTION
                item.error_message = str(exc)[:1000]
                item.claim_key = None
                item.finished_at = _now()
                self.db.commit()

        self.db.refresh(batch)
        self._recompute_stats(batch)
        self.db.commit()
        self.db.refresh(batch)
        return {"batch_id": batch_id, "status": batch.status, "stats": self._stats_dict(batch)}

    def _execute_item(self, item: QuestionReviewBatchItem) -> None:
        """执行单个批次项：资格跳过不伪造决策记录（§5.3），真实审核走单题服务。"""
        question = self.db.query(Question).filter(Question.id == item.question_id).first()
        if not question:
            self._skip_item(item, "question_not_found")
            return

        verdict, code = self._review_service.check_eligibility(question)
        if verdict != "eligible":
            # 资格跳过：仅存 BatchItem 原因，不产生 question_review_record（§5.3）
            self._skip_item(item, code)
            return

        review_round = self._review_service.allocate_review_round(question.id)
        result = self._review_service.review_one(
            question.id,
            task_id=None,
            review_round=review_round,
            trigger_source="manual_batch",
            batch_id=item.batch_id,
        )

        status = result.get("execution_status")
        record_id = result.get("record_id")
        if status == "success":
            item.status = "completed"
            item.review_record_id = record_id
        elif status == "skipped":
            # review_one 内部二次准入判定跳过（竞态兜底，decision=None 非伪造）
            self._skip_item(item, result.get("error_code") or "skipped", record_id=record_id)
            return
        else:
            item.status = "failed"
            item.review_record_id = record_id
            item.error_code = result.get("error_code") or FAIL_EXECUTION
            item.error_message = (result.get("reason") or "")[:1000]
        item.claim_key = None
        item.finished_at = _now()
        self.db.commit()

    def _skip_item(self, item: QuestionReviewBatchItem, code: str, record_id: Optional[int] = None) -> None:
        item.status = "skipped"
        item.skip_reason = code
        item.review_record_id = record_id
        item.claim_key = None
        item.finished_at = _now()
        self.db.commit()

    # ------------------------------------------------------------------
    # 统计（§8）：全部由 BatchItem 重算派生，幂等可核对
    # ------------------------------------------------------------------
    def _recompute_stats(self, batch: QuestionReviewBatch) -> None:
        items = (
            self.db.query(QuestionReviewBatchItem)
            .filter(QuestionReviewBatchItem.batch_id == batch.id)
            .all()
        )
        # accepted = 接纳执行的项（queued/running/completed/failed），skipped 为未接纳
        accepted = sum(1 for i in items if i.claim_key == CLAIM_KEY_ACTIVE or i.status in ("completed", "failed"))
        processed = 0
        auto_approved = auto_rejected = manual = 0
        failed = skipped = pending = 0
        for i in items:
            if i.status == "skipped":
                skipped += 1
            elif i.status == "failed":
                failed += 1
            elif i.status in ITEM_ACTIVE_STATUSES:
                pending += 1
            elif i.status == "completed":
                processed += 1
                rec = (
                    self.db.query(QuestionReviewRecord)
                    .filter(QuestionReviewRecord.id == i.review_record_id)
                    .first()
                    if i.review_record_id
                    else None
                )
                decision = (rec.decision if rec else None) or "manual_review"
                if decision == "auto_approve":
                    auto_approved += 1
                elif decision == "auto_reject":
                    auto_rejected += 1
                else:
                    manual += 1

        batch.total_count = len(items)
        batch.accepted_count = accepted
        batch.processed_count = processed
        batch.auto_approved_count = auto_approved
        batch.auto_rejected_count = auto_rejected
        batch.manual_review_count = manual
        batch.failed_count = failed
        batch.skipped_count = skipped
        batch.pending_count = pending

        # 批次状态（§5）：created→queued（不在此提升为 running，running 由
        # execute 显式置位）；completed=全部执行完成（允许部分 skipped）；
        # partial=部分成功部分失败；failed=全部失败/执行器异常
        if pending > 0:
            pass  # 保持 queued（未执行）/ running（执行中）
        else:
            if failed == 0:
                batch.status = "completed"
            elif processed > 0:
                batch.status = "partial"
            else:
                batch.status = "failed"
            batch.finished_at = batch.finished_at or _now()

    def _stats_dict(self, batch: QuestionReviewBatch) -> Dict[str, Any]:
        return {
            "total": batch.total_count,
            "accepted": batch.accepted_count,
            "processed": batch.processed_count,
            "auto_approved": batch.auto_approved_count,
            "auto_rejected": batch.auto_rejected_count,
            "manual_review": batch.manual_review_count,
            "failed": batch.failed_count,
            "skipped": batch.skipped_count,
            "pending": batch.pending_count,
        }

    # ------------------------------------------------------------------
    # 重启恢复（§8）：卡死批次明确恢复，不静默、不永久挂起
    # ------------------------------------------------------------------
    def recover_incomplete_batches(self) -> Dict[str, Any]:
        """服务启动时调用：把 queued/running 批次中未完成的项标记为中断失败并释放认领。

        管理员随后可重新发起新批次（失败不无限重试，§7 幂等条款）。
        """
        batches = (
            self.db.query(QuestionReviewBatch)
            .filter(QuestionReviewBatch.status.in_(BATCH_ACTIVE_STATUSES))
            .all()
        )
        recovered_items = 0
        for batch in batches:
            stuck = (
                self.db.query(QuestionReviewBatchItem)
                .filter(
                    QuestionReviewBatchItem.batch_id == batch.id,
                    QuestionReviewBatchItem.status.in_(ITEM_ACTIVE_STATUSES),
                )
                .all()
            )
            for item in stuck:
                item.status = "failed"
                item.error_code = INTERRUPTED_CODE
                item.error_message = "服务重启导致执行中断，已释放题目认领；请重新发起批量审核"
                item.claim_key = None
                item.finished_at = _now()
                recovered_items += 1
            self._recompute_stats(batch)
        self.db.commit()
        return {"recovered_batches": len(batches), "recovered_items": recovered_items}

    # ------------------------------------------------------------------
    # 查询（§6.4/§6.5）
    # ------------------------------------------------------------------
    def list_batches(
        self,
        status: Optional[str] = None,
        created_by: Optional[int] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Dict[str, Any]], int]:
        query = self.db.query(QuestionReviewBatch)
        if status:
            query = query.filter(QuestionReviewBatch.status == status)
        if created_by:
            query = query.filter(QuestionReviewBatch.created_by == created_by)
        total = query.count()
        rows = (
            query.order_by(QuestionReviewBatch.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return [self._batch_to_dict(b) for b in rows], total

    def get_batch_detail(self, batch_id: int) -> Optional[Dict[str, Any]]:
        batch = self._get_batch(batch_id)
        if not batch:
            return None
        items = (
            self.db.query(QuestionReviewBatchItem)
            .filter(QuestionReviewBatchItem.batch_id == batch_id)
            .order_by(QuestionReviewBatchItem.id)
            .all()
        )
        item_dicts = [self._item_to_dict(i) for i in items]
        detail = self._batch_to_dict(batch)
        detail["progress"] = {
            "processed": batch.processed_count,
            "accepted": batch.accepted_count,
            "pending": batch.pending_count,
        }
        detail["items"] = item_dicts
        return detail

    @staticmethod
    def _batch_to_dict(b: QuestionReviewBatch) -> Dict[str, Any]:
        return {
            "id": b.id,
            "created_by": b.created_by,
            "status": b.status,
            "total_count": b.total_count,
            "accepted_count": b.accepted_count,
            "processed_count": b.processed_count,
            "auto_approved_count": b.auto_approved_count,
            "auto_rejected_count": b.auto_rejected_count,
            "manual_review_count": b.manual_review_count,
            "failed_count": b.failed_count,
            "skipped_count": b.skipped_count,
            "pending_count": b.pending_count,
            "started_at": b.started_at.isoformat() if b.started_at else None,
            "finished_at": b.finished_at.isoformat() if b.finished_at else None,
            "error_message": b.error_message,
            "created_at": b.created_at.isoformat() if b.created_at else None,
            "updated_at": b.updated_at.isoformat() if b.updated_at else None,
        }

    def _item_to_dict(self, i: QuestionReviewBatchItem) -> Dict[str, Any]:
        question = self.db.query(Question).filter(Question.id == i.question_id).first()
        record = (
            self.db.query(QuestionReviewRecord)
            .filter(QuestionReviewRecord.id == i.review_record_id)
            .first()
            if i.review_record_id
            else None
        )
        return {
            "id": i.id,
            "question_id": i.question_id,
            "question_content": (question.content or "")[:120] if question else None,
            "question_type": question.question_type if question else None,
            "question_status": question.status if question else None,
            "status": i.status,
            "skip_reason": i.skip_reason,
            "skip_reason_text": _reason_text(i.skip_reason) if i.skip_reason else None,
            "error_code": i.error_code,
            "error_message": i.error_message,
            "review_record_id": i.review_record_id,
            "review_decision": record.decision if record else None,
            "review_risk_level": record.risk_level if record else None,
            "review_reason": record.reason if record else None,
            "review_issue_types": (record.issue_types or []) if record else [],
            "review_evidence_summary": (
                [
                    {"knowledge_id": e.get("knowledge_id"), "explanation": (e.get("explanation") or "")[:120]}
                    for e in (record.evidence or [])
                ]
                if record
                else []
            ),
            "started_at": i.started_at.isoformat() if i.started_at else None,
            "finished_at": i.finished_at.isoformat() if i.finished_at else None,
        }

    def _check_one(self, question_id: int) -> Tuple[bool, str]:
        """准入预检/创建校验（复用单题服务 check_eligibility）。"""
        question = self.db.query(Question).filter(Question.id == question_id).first()
        if not question:
            return False, "question_not_found"
        verdict, code = self._review_service.check_eligibility(question)
        return verdict == "eligible", ("" if verdict == "eligible" else code)

    def _get_batch(self, batch_id: int) -> Optional[QuestionReviewBatch]:
        return (
            self.db.query(QuestionReviewBatch)
            .filter(QuestionReviewBatch.id == batch_id)
            .first()
        )
