"""题目 AI 质量审核服务（执行文档 §2/§5/§6）。

职责：
- 审核准入判断（去重优先于 AI 审核，§2.1）；
- 调用 QuestionReviewAgent（纯审核层）；
- 保存 question_review_record 审核记录（追加式审计）；
- 执行题目状态流转（auto_approve→published / auto_reject→rejected，带二次保护）；
- 更新任务审核统计。

安全原则：
- 任何执行失败/超时/解析失败 → fail-safe 保持 pending_review，绝不自动通过、绝不以技术异常驳回；
- 无审核记录不允许自动发布/自动驳回；
- 人工已处理的题目不能被延迟 AI 审核覆盖（条件更新 WHERE status='pending_review'）。
"""

import hashlib
import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import or_
from sqlalchemy.orm import Session

from agent.common.config import agent_settings
from agent.question_review.agent import (
    QuestionReviewAgent,
    QuestionReviewAgentError,
)
from agent.question_review.schemas import ISSUE_TYPES, QuestionReviewOutput
from app.models.question import Question
from app.models.question_dedup_record import QuestionDedupRecord as QDR
from app.models.question_generation_task import QuestionGenerationTask
from app.models.question_knowledge import QuestionKnowledge
from app.models.question_option import QuestionOption
from app.models.question_review_record import QuestionReviewRecord

logger = logging.getLogger(__name__)

# 第一版自动审核题型范围（§4.5）：简答题不自动发布/驳回
SUPPORTED_QUESTION_TYPES = ("SINGLE_CHOICE", "MULTIPLE_CHOICE", "TRUE_FALSE")

# 跳过原因（error_code 语义复用）
SKIP_UNSUPPORTED_TYPE = "unsupported_question_type"
SKIP_DEDUP_UNRESOLVED = "dedup_unresolved"
SKIP_DEDUP_DUPLICATE = "dedup_duplicate"
SKIP_BUDGET_EXCEEDED = "budget_exceeded"
FAIL_EXECUTION = "execution_failed"
FAIL_CONTENT_CHANGED = "content_changed_during_review"


class QuestionReviewService:
    """题目 AI 质量审核服务。"""

    def __init__(self, db: Session, *, agent=None) -> None:
        self.db = db
        self._agent = agent

    # ------------------------------------------------------------------
    # 准入判断（§2.1：去重优先于 AI 审核）
    # ------------------------------------------------------------------
    def check_eligibility(self, question: Question) -> Tuple[str, str]:
        """返回 (verdict, reason_code)。

        verdict:
        - "eligible"：可进入 AI 审核；
        - "skipped"：跳过（reason_code=unsupported_question_type/dedup_unresolved/dedup_duplicate）。
        """
        if question.question_type not in SUPPORTED_QUESTION_TYPES:
            return "skipped", SKIP_UNSUPPORTED_TYPE

        verdict, code, _ = self._dedup_gate(question)
        if not verdict:
            return "skipped", code
        return "eligible", ""

    def _dedup_gate(self, question: Question) -> Tuple[bool, str, str]:
        """去重疑点聚合判断（§2.1.4/§2.1.5）。

        返回 (通过, 原因码, 去重状态描述)：
        - 任一关联记录 needs_manual_review=True 且未被人工裁定 → 不准入（dedup_unresolved）；
        - 任一关联记录 effective_decision=duplicate → 不准入且禁止发布（dedup_duplicate）；
        - effective_decision = manual_resolution or decision（人工结论优先）。
        """
        rows = self.db.query(QDR).filter(
            or_(
                QDR.matched_question_id == question.id,
                QDR.new_content_hash == question.content_hash,
            )
        ).all()

        if not rows:
            return True, "", "clean"

        effective_values = []
        for row in rows:
            effective = row.manual_resolution or row.decision
            effective_values.append(effective or "unknown")
            if row.needs_manual_review:
                return False, SKIP_DEDUP_UNRESOLVED, "/".join(effective_values)
            if effective == "duplicate":
                return False, SKIP_DEDUP_DUPLICATE, "/".join(effective_values)

        if "uncertain" in effective_values:
            # 决策为 uncertain 但 needs_manual_review 已被人工处理（裁定 distinct）
            return True, "", "/".join(effective_values)
        return True, "", "/".join(effective_values)

    # ------------------------------------------------------------------
    # 内容指纹（§5.2.3：审核期间题干/选项/答案/解析/知识点关联不得变化）
    # ------------------------------------------------------------------
    @staticmethod
    def review_content_hash(db: Session, question: Question) -> str:
        from app.services.question_normalizer import question_normalizer

        options = (
            db.query(QuestionOption)
            .filter(QuestionOption.question_id == question.id)
            .order_by(QuestionOption.sort_order)
            .all()
        )
        base_hash = question_normalizer.compute_content_hash(
            question.question_type,
            question.content or "",
            question.answer or "",
            [(o.option_content, 1 if o.is_correct else 0) for o in options],
        )
        knowledge_ids = sorted(
            kq.knowledge_id
            for kq in db.query(QuestionKnowledge)
            .filter(QuestionKnowledge.question_id == question.id)
            .all()
        )
        payload = json.dumps(
            {
                "base": base_hash,
                "analysis": question.analysis or "",
                "knowledge_ids": knowledge_ids,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]

    # ------------------------------------------------------------------
    # 单题审核
    # ------------------------------------------------------------------
    def review_one(
        self,
        question_id: int,
        task_id: Optional[int] = None,
        review_round: int = 1,
    ) -> Dict[str, Any]:
        """审核单题并按决策执行状态流转。返回审核结果 dict。"""
        question = self.db.query(Question).filter(Question.id == question_id).first()
        if not question:
            return {"question_id": question_id, "execution_status": "failed",
                    "error_code": "question_not_found", "decision": None}

        # 幂等（§8）：同一题同一轮次只执行一次
        existing = (
            self.db.query(QuestionReviewRecord)
            .filter(
                QuestionReviewRecord.question_id == question_id,
                QuestionReviewRecord.review_round == review_round,
            )
            .first()
        )
        if existing:
            return self._record_to_result(existing)

        # 准入
        verdict, skip_code = self.check_eligibility(question)
        if verdict == "skipped":
            record = self._save_record(
                question=question,
                task_id=task_id,
                review_round=review_round,
                execution_status="skipped",
                decision=None,
                error_code=skip_code,
                error_message=f"跳过 AI 审核: {skip_code}",
                reviewed_content_hash=self.review_content_hash(self.db, question),
            )
            self.db.commit()
            return self._record_to_result(record)

        # 构建审核上下文（§4.2）并执行
        content_hash_before = self.review_content_hash(self.db, question)
        context = self._build_context(question, content_hash_before)
        started = time.monotonic()
        try:
            output = self.get_agent().review(context)
        except QuestionReviewAgentError as exc:
            # fail-safe（§4.3/§9）：执行失败保持 pending_review，不自动通过/驳回
            duration_ms = int((time.monotonic() - started) * 1000)
            record = self._save_record(
                question=question,
                task_id=task_id,
                review_round=review_round,
                execution_status="failed",
                decision=None,
                error_code=FAIL_EXECUTION,
                error_message=str(exc)[:1000],
                reviewed_content_hash=content_hash_before,
                duration_ms=duration_ms,
            )
            self.db.commit()
            return self._record_to_result(record)
        duration_ms = int((time.monotonic() - started) * 1000)

        # 服务端决策规则复核（§4.4）：模型自相矛盾时不得执行自动流转
        decision = self._normalize_decision(output)
        issue_types = [i for i in output.issue_types if i in ISSUE_TYPES] or (
            list(output.issue_types) if output.issue_types else []
        )

        record = self._save_record(
            question=question,
            task_id=task_id,
            review_round=review_round,
            execution_status="success",
            decision=decision,
            risk_level=output.risk_level,
            issue_types=issue_types,
            checks=output.checks.model_dump(),
            reason=(output.reason or "")[:2000],
            evidence=[e.model_dump() for e in output.evidence],
            reviewed_content_hash=content_hash_before,
            duration_ms=duration_ms,
        )

        # 状态流转（auto_approve/auto_reject 带二次保护；manual_review 保持 pending_review）
        transition = self._apply_decision(question, decision, content_hash_before)
        self.db.commit()
        result = self._record_to_result(record)
        result["transition"] = transition
        return result

    # ------------------------------------------------------------------
    # 决策规则复核（§4.4）
    # ------------------------------------------------------------------
    @staticmethod
    def _normalize_decision(output: QuestionReviewOutput) -> str:
        checks = output.checks.model_dump()
        values = list(checks.values())
        has_fail = any(v == "fail" for v in values)
        all_applicable_pass = all(v in ("pass", "not_applicable") for v in values)
        has_issues = bool(output.issue_types)
        has_reason = bool((output.reason or "").strip())
        has_evidence = bool(output.evidence)

        if output.decision == "auto_approve":
            # 仅当全部检查 pass/不适用、无问题项、低风险才允许自动通过
            if all_applicable_pass and not has_issues and output.risk_level == "low":
                return "auto_approve"
            return "manual_review"

        if output.decision == "auto_reject":
            # 仅当存在失败检查 + 问题类型 + 理由 + 证据，才允许自动驳回
            if has_fail and has_issues and has_reason and has_evidence:
                return "auto_reject"
            return "manual_review"

        return "manual_review"

    # ------------------------------------------------------------------
    # 状态流转（§5.2/§5.3）
    # ------------------------------------------------------------------
    def _apply_decision(self, question: Question, decision: str, content_hash_before: str) -> Dict[str, Any]:
        if decision == "manual_review":
            return {"applied": False, "status": question.status, "reason": "manual_review"}

        # 二次保护 3：审核期间内容变化 → 不流转
        content_hash_now = self.review_content_hash(self.db, question)
        if content_hash_now != content_hash_before:
            return {"applied": False, "status": question.status,
                    "reason": FAIL_CONTENT_CHANGED}

        # 二次保护 2：复查去重疑点（审核期间可能被人工裁定）
        gate_ok, gate_code, _ = self._dedup_gate(question)
        if not gate_ok:
            return {"applied": False, "status": question.status, "reason": gate_code}

        target_status = "published" if decision == "auto_approve" else "rejected"

        # 二次保护 1/4：条件更新（原子）——仅当仍为 pending_review
        updated = (
            self.db.query(Question)
            .filter(Question.id == question.id, Question.status == "pending_review")
            .update({"status": target_status}, synchronize_session=False)
        )
        if not updated:
            # 人工已处理（发布/驳回/下架），迟到的 AI 审核不得覆盖（§5.3）
            self.db.rollback()
            return {"applied": False, "status": "changed",
                    "reason": "question_status_changed_by_human"}

        self.db.refresh(question)
        # 状态同步：发布=登记 dedup_key+向量索引；驳回=解除阻断
        from app.services.question_dedup_service import sync_question_dedup_state
        sync_question_dedup_state(self.db, question)
        return {"applied": True, "status": question.status, "reason": ""}

    # ------------------------------------------------------------------
    # 任务级审核（§6/§8）
    # ------------------------------------------------------------------
    def run_task_review(self, task_id: int) -> Dict[str, Any]:
        """对本次任务生成并入库的题目执行 AI 审核，更新任务统计。"""
        task = self.db.query(QuestionGenerationTask).filter(
            QuestionGenerationTask.id == task_id
        ).first()
        if not task:
            return {"task_id": task_id, "error": "task_not_found"}

        if not task.enable_ai_review:
            task.ai_review_status = "not_requested"
            self.db.commit()
            return {"task_id": task_id, "ai_review_status": "not_requested", "stats": {}}

        task.ai_review_status = "running"
        self.db.commit()

        # 只统计进入本次任务审核阶段的题目：本次任务生成并入库的题（去重淘汰候选不在此列）
        questions = (
            self.db.query(Question)
            .filter(Question.generation_task_id == task_id)
            .order_by(Question.id)
            .all()
        )
        budget = int(agent_settings.QUESTION_AI_REVIEW_MAX_PER_TASK)

        stats = {
            "total": len(questions),
            "processed": 0,
            "auto_approved": 0,
            "auto_rejected": 0,
            "manual_review": 0,
            "failed": 0,
            "skipped": 0,
            "pending": 0,
        }

        for idx, question in enumerate(questions):
            if idx >= budget:
                # 超出成本预算：跳过并记录（§9 每任务最大审核量）
                record = self._save_record(
                    question=question,
                    task_id=task_id,
                    review_round=self._next_round(question.id),
                    execution_status="skipped",
                    decision=None,
                    error_code=SKIP_BUDGET_EXCEEDED,
                    error_message=f"超出每任务审核预算 {budget}",
                    reviewed_content_hash=self.review_content_hash(self.db, question),
                )
                self.db.commit()
                stats["skipped"] += 1
                continue

            try:
                result = self.review_one(question.id, task_id=task_id)
            except Exception as exc:  # noqa: BLE001 单题失败不影响其余题（§8）
                logger.error(f"题目 {question.id} AI 审核异常: {exc}", exc_info=True)
                self.db.rollback()
                stats["failed"] += 1
                continue

            status = result.get("execution_status")
            if status == "success":
                stats["processed"] += 1
                decision = result.get("decision")
                if decision == "auto_approve":
                    stats["auto_approved"] += 1
                elif decision == "auto_reject":
                    stats["auto_rejected"] += 1
                else:
                    stats["manual_review"] += 1
            elif status == "skipped":
                stats["skipped"] += 1
            else:
                stats["failed"] += 1

        stats["pending"] = max(0, stats["total"] - stats["processed"] - stats["skipped"] - stats["failed"])

        # 统计口径：与持久化审核记录保持一致
        task.ai_review_total_count = stats["total"]
        task.ai_review_processed_count = stats["processed"]
        task.ai_auto_approved_count = stats["auto_approved"]
        task.ai_auto_rejected_count = stats["auto_rejected"]
        task.ai_manual_review_count = stats["manual_review"]
        task.ai_review_failed_count = stats["failed"]
        task.ai_review_skipped_count = stats["skipped"]
        task.ai_review_pending_count = stats["pending"]
        # completed 即使产生 manual_review 题目也算执行完成（§6）
        if stats["failed"] == 0:
            task.ai_review_status = "completed"
        elif stats["processed"] > 0:
            task.ai_review_status = "partial"
        else:
            task.ai_review_status = "failed"
        self.db.commit()

        return {"task_id": task_id, "ai_review_status": task.ai_review_status, "stats": stats}

    # ------------------------------------------------------------------
    # 工具方法
    # ------------------------------------------------------------------
    def get_agent(self):
        if self._agent is not None:
            return self._agent
        self._agent = QuestionReviewAgent()
        return self._agent

    def _next_round(self, question_id: int) -> int:
        max_round = (
            self.db.query(QuestionReviewRecord.review_round)
            .filter(QuestionReviewRecord.question_id == question_id)
            .order_by(QuestionReviewRecord.review_round.desc())
            .first()
        )
        return (max_round[0] if max_round else 0) + 1

    def _build_context(self, question: Question, _content_hash: str) -> Dict[str, Any]:
        """组装审核上下文（§4.2）。不含其他题目的答案或人工裁定结论。"""
        options = (
            self.db.query(QuestionOption)
            .filter(QuestionOption.question_id == question.id)
            .order_by(QuestionOption.sort_order)
            .all()
        )
        knowledge_ids = [
            qk.knowledge_id
            for qk in self.db.query(QuestionKnowledge)
            .filter(QuestionKnowledge.question_id == question.id)
            .all()
        ]
        knowledge_points: List[Dict[str, Any]] = []
        if knowledge_ids:
            from app.models.knowledge import Knowledge
            rows = (
                self.db.query(Knowledge)
                .filter(Knowledge.id.in_(knowledge_ids))
                .all()
            )
            for k in rows:
                knowledge_points.append({
                    "knowledge_id": k.id,
                    "name": k.name,
                    "content": k.content or "",
                    "importance_level": getattr(k, "importance_level", "normal") or "normal",
                })

        gate_ok, gate_code, dedup_status = self._dedup_gate(question)

        return {
            "question_id": question.id,
            "question_type": question.question_type,
            "difficulty": question.difficulty,
            "content": question.content or "",
            "answer": question.answer or "",
            "analysis": question.analysis,
            "options": [
                {
                    "option_key": o.option_key,
                    "option_content": o.option_content,
                    "is_correct": bool(o.is_correct),
                }
                for o in options
            ],
            "knowledge_points": knowledge_points,
            "version_environment": None,
            "dedup_status": dedup_status,
            "dedup_unresolved": not gate_ok and gate_code == SKIP_DEDUP_UNRESOLVED,
        }

    def _save_record(
        self,
        *,
        question: Question,
        task_id: Optional[int],
        review_round: int,
        execution_status: str,
        decision: Optional[str],
        risk_level: Optional[str] = None,
        issue_types: Optional[list] = None,
        checks: Optional[dict] = None,
        reason: Optional[str] = None,
        evidence: Optional[list] = None,
        reviewed_content_hash: Optional[str] = None,
        duration_ms: Optional[int] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> QuestionReviewRecord:
        record = QuestionReviewRecord(
            question_id=question.id,
            generation_task_id=task_id,
            review_round=review_round,
            trigger_source="generation_task",
            execution_status=execution_status,
            decision=decision,
            risk_level=risk_level,
            issue_types=issue_types,
            checks=checks,
            reason=reason,
            evidence=evidence,
            model_name=self._model_name(),
            prompt_version=self._prompt_version(),
            reviewed_content_hash=reviewed_content_hash,
            duration_ms=duration_ms,
            error_code=error_code,
            error_message=error_message,
        )
        self.db.add(record)
        self.db.flush()
        return record

    def _model_name(self) -> str:
        try:
            return (
                agent_settings.QUESTION_AI_REVIEW_MODEL
                or agent_settings.LLM_MODEL
                or ""
            )
        except Exception:  # noqa: BLE001
            return ""

    @staticmethod
    def _prompt_version() -> str:
        from agent.question_review.prompts import REVIEW_PROMPT_VERSION
        return REVIEW_PROMPT_VERSION

    @staticmethod
    def _record_to_result(record: QuestionReviewRecord) -> Dict[str, Any]:
        return {
            "record_id": record.id,
            "question_id": record.question_id,
            "review_round": record.review_round,
            "execution_status": record.execution_status,
            "decision": record.decision,
            "risk_level": record.risk_level,
            "issue_types": record.issue_types or [],
            "reason": record.reason,
            "error_code": record.error_code,
            "duration_ms": record.duration_ms,
        }
