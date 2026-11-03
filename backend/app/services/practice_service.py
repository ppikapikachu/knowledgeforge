"""练习服务：组卷快照 / 练习会话 / 草稿标记 / 提交判分。

硬性设计约束（来自 docs/14 开发文档）：
    - 组卷只查询 published + 开放题库题目，不调用 LLM/Agent，不补题
    - 快照不可变：判分与回顾一律读 practice_paper_item.question_snapshot，
      不实时读 question 表，源题后续变化不影响历史判分
    - practice_session 必须关联 practice_paper_id
    - 判分以快照标准答案为准；简答不自动判分
    - 会话计数由 practice_session_item 统一函数重算（幂等）
    - 所有查询带 owner_user_id 条件（owner 专属）
"""

import hashlib
import json
import random
import re
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import (
    ResourceNotFoundException,
    ValidationException,
)
from app.models.knowledge import Knowledge
from app.models.practice_paper import PracticePaper
from app.models.practice_paper_item import PracticePaperItem
from app.models.practice_session import PracticeSession
from app.models.practice_session_item import PracticeSessionItem
from app.models.question import Question
from app.models.question_answer_record import QuestionAnswerRecord
from app.models.question_bank import QuestionBank
from app.models.question_knowledge import QuestionKnowledge
from app.models.question_option import QuestionOption
from app.services.grading_service import coerce_answer, judge, normalize_bool_answer

DIFFICULTY_NAME_TO_CODE = {"easy": 1, "normal": 2, "hard": 3}
DIFFICULTY_CODE_TO_NAME = {1: "easy", 2: "normal", 3: "hard"}
VALID_TYPES = ("SINGLE_CHOICE", "MULTIPLE_CHOICE", "TRUE_FALSE", "SHORT_ANSWER")

# 敏感字段白名单投影：未提交的题目不得返回 correct_answer/explanation，
# 禁止把 ORM 对象直接序列化成 JSON 返回。
ITEM_PUBLIC_KEYS = (
    "paper_item_id", "sort_order", "question_type", "difficulty",
    "difficulty_name", "score", "content", "options", "knowledge_points",
)


def _snapshot_item_payload(
    question: Question,
    options: List[QuestionOption],
    knowledge_points: List[dict],
    score: Decimal,
) -> dict:
    """构建一道题的完整快照（含正确答案/解析，仅供服务端判分与提交后返回）。"""
    q_type = question.question_type
    if q_type in ("SINGLE_CHOICE", "MULTIPLE_CHOICE"):
        correct_keys = sorted(
            o.option_key for o in options if o.is_correct
        )
        correct_answer = ",".join(correct_keys)
    elif q_type == "TRUE_FALSE":
        correct_answer = normalize_bool_answer(question.answer)
    else:
        correct_answer = question.answer or ""

    return {
        "question_id": question.id,
        "question_type": q_type,
        "difficulty": question.difficulty,
        "content": question.content,
        "options": [
            {
                "option_key": o.option_key,
                "content": o.option_content,
                "is_correct": bool(o.is_correct),
            }
            for o in sorted(
                options,
                key=lambda x: (
                    x.sort_order if x.sort_order is not None else 999,
                    x.option_key or "",
                ),
            )
        ],
        "correct_answer": correct_answer,
        "explanation": question.explanation or "",
        "knowledge_points": knowledge_points,
        "score": float(score),
    }


def item_public_projection(item: PracticePaperItem) -> dict:
    """题目快照的对外白名单投影（不含 correct_answer/explanation/is_correct）。"""
    snap = item.question_snapshot or {}
    return {
        "paper_item_id": item.id,
        "sort_order": item.sort_order,
        "question_type": item.question_type,
        "difficulty": item.difficulty,
        "difficulty_name": DIFFICULTY_CODE_TO_NAME.get(item.difficulty, "normal"),
        "score": float(item.score),
        "content": snap.get("content", ""),
        "options": [
            {"option_key": o.get("option_key"), "content": o.get("content")}
            for o in snap.get("options", [])
        ],
        "knowledge_points": snap.get("knowledge_points", []),
    }


def item_result_projection(
    item: PracticePaperItem,
    session_item: Optional[PracticeSessionItem],
) -> dict:
    """提交后的题目结果投影（含正确答案/解析/用户答案/判分结果）。"""
    snap = item.question_snapshot or {}
    base = item_public_projection(item)
    base.update({
        "correct_answer": snap.get("correct_answer"),
        "explanation": snap.get("explanation"),
        "your_answer": (
            (session_item.draft_answer or {}).get("answer")
            if session_item and session_item.draft_answer else None
        ),
        "is_correct": (
            bool(session_item.latest_is_correct)
            if session_item and session_item.latest_is_correct is not None else None
        ),
        "grading_status": session_item.latest_grading_status if session_item else None,
        "first_submitted_at": (
            session_item.first_submitted_at.isoformat()
            if session_item and session_item.first_submitted_at else None
        ),
        "last_submitted_at": (
            session_item.last_submitted_at.isoformat()
            if session_item and session_item.last_submitted_at else None
        ),
    })
    return base


def item_projection_for_state(
    item: PracticePaperItem,
    session_item: Optional[PracticeSessionItem],
    session_status: str,
) -> dict:
    """§8 结果答案安全的统一投影：按会话状态决定是否可见正确答案。

    - completed：全量回顾（result 投影，含 correct_answer/explanation/判分结果）
    - in_progress / abandoned：仅"已提交（answered）"的题给结果投影；
      未提交（unanswered/draft_saved）一律 public 投影，
      绝不返回 correct_answer/explanation/is_correct

    所有会话/结果出口统一走本函数，禁止在调用处临时 pop 字段。
    """
    if session_status == "completed":
        return item_result_projection(item, session_item)
    if session_item is not None and session_item.status == "answered":
        return item_result_projection(item, session_item)
    return item_public_projection(item)


class PracticeService:
    """组卷快照与练习会话服务。"""

    def __init__(self, db: Session):
        self.db = db

    # ==================== 组卷 ====================

    def assemble_paper(
        self,
        user_id: int,
        question_bank_id: Optional[int],
        title: Optional[str],
        question_type_counts: Dict[str, int],
        difficulty_distribution: Dict[str, int],
        total_count: int,
        knowledge_ids: Optional[List[int]] = None,
        allow_partial: bool = False,
        idempotency_key: Optional[str] = None,
    ) -> dict:
        """组卷入口（只读 published 题快照，不调用 LLM/Agent/补题）。

        校验顺序（docs/14 补充开发文档 §6.2）：Idempotency-Key 格式 → 题库存在且开放练习
        → 题型/难度合法性（Schema 层）→ total_count 与两个分布一致 → knowledge_ids 归属
        → 幂等比对 → 库存（allow_partial=false 时零落库）→ 事务原子构建。

        幂等语义（§6.1）：同用户同 key 同参数返回原卷（不重复抽题）；同 key 异参数返回
        40001 幂等冲突（绝不悄悄返回旧卷）；不同用户同 key 互不影响（查询限定 owner）；
        并发写入由唯一约束 (owner_user_id, idempotency_key) 兜底，捕获后重读比较请求签名。
        """
        idempotency_key = self._validate_idempotency_key(idempotency_key)

        title_final = (title or "").strip() or f"练习卷 {datetime.utcnow():%Y-%m-%d %H:%M}"
        title_final = title_final[:128]

        # 题库必须存在且开放练习；未开放与不存在返回同一错误，不泄露私有题库存在性
        if question_bank_id is None:
            raise ValidationException("question_bank_id 必填：请选择已开放练习的题库")
        bank = (
            self.db.query(QuestionBank)
            .filter(QuestionBank.id == question_bank_id)
            .first()
        )
        if not bank or not bool(bank.is_available_for_practice):
            raise ValidationException("题库不存在或未开放练习")

        type_needs = self._normalize_counts(question_type_counts)
        diff_needs = self._normalize_difficulty(difficulty_distribution)
        if sum(type_needs.values()) != total_count:
            raise ValidationException("total_count 必须与题型数量之和一致")
        if sum(diff_needs.values()) != total_count:
            raise ValidationException("total_count 必须与难度分布之和一致")

        # 知识点归属：每个 knowledge_id 必须与指定题库存在真实关联（该题库 published 题的真实关联），
        # 无效 ID 明确参数错误，不静默忽略
        kid_list = list(dict.fromkeys(int(k) for k in (knowledge_ids or [])))
        if kid_list:
            allowed_ids = {
                row[0]
                for row in (
                    self.db.query(QuestionKnowledge.knowledge_id)
                    .join(Question, Question.id == QuestionKnowledge.question_id)
                    .filter(
                        Question.question_bank_id == question_bank_id,
                        Question.status == "published",
                    )
                    .distinct()
                    .all()
                )
            }
            invalid = [k for k in kid_list if k not in allowed_ids]
            if invalid:
                raise ValidationException(f"知识点不属于该题库或无已发布题目: {invalid}")

        signature = self._assembly_signature(
            question_bank_id, kid_list, type_needs, diff_needs, total_count
        )

        # 幂等比对：同 key 同参返回原卷；同 key 异参明确冲突
        if idempotency_key:
            existing = (
                self.db.query(PracticePaper)
                .filter(
                    PracticePaper.owner_user_id == user_id,
                    PracticePaper.idempotency_key == idempotency_key,
                )
                .first()
            )
            if existing:
                return self._idempotent_response(existing, signature)

        # 候选池：published + 指定开放题库 + 可选知识点过滤（不调用 LLM）
        pool_query = self.db.query(Question).filter(
            Question.status == "published",
            Question.question_bank_id == question_bank_id,
        )
        if kid_list:
            kid_filter = (
                self.db.query(QuestionKnowledge.question_id)
                .filter(QuestionKnowledge.knowledge_id.in_(kid_list))
                .subquery()
            )
            pool_query = pool_query.filter(Question.id.in_(kid_filter))
        pool = pool_query.all()
        pool_by_id = {q.id: q for q in pool}

        # 各边际可用量校验（题型 / 难度），库存不足默认明确报错不静默少题
        type_avail = {t: 0 for t in type_needs}
        diff_avail = {d: 0 for d in diff_needs}
        for q in pool:
            if q.question_type in type_avail:
                type_avail[q.question_type] += 1
            if q.difficulty in diff_avail:
                diff_avail[q.difficulty] += 1

        missing = 0
        for t, need in type_needs.items():
            if type_avail.get(t, 0) < need:
                missing += need - type_avail.get(t, 0)
        for d, need in diff_needs.items():
            if diff_avail.get(d, 0) < need:
                missing += need - diff_avail.get(d, 0)
        available_count = min(len(pool), total_count)
        if missing > 0 and not allow_partial:
            return {
                "error": "insufficient_stock",
                "requested_count": total_count,
                "available_count": available_count,
                "missing_count": missing,
            }

        selected_ids = self._select_questions(pool, type_needs, diff_needs, total_count)

        # 并发幂等兜底：唯一约束冲突（另一请求已用同 key 落库）→ rollback 重读比较签名
        try:
            paper, items, session = self._build_paper(
                user_id=user_id,
                question_bank_id=question_bank_id,
                title=title_final,
                selected_ids=selected_ids,
                pool_by_id=pool_by_id,
                type_needs=type_needs,
                diff_needs=diff_needs,
                knowledge_ids=kid_list,
                idempotency_key=idempotency_key,
                total_count=total_count,
            )
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            if idempotency_key:
                existing = (
                    self.db.query(PracticePaper)
                    .filter(
                        PracticePaper.owner_user_id == user_id,
                        PracticePaper.idempotency_key == idempotency_key,
                    )
                    .first()
                )
                if existing:
                    return self._idempotent_response(existing, signature)
            raise ValidationException("组卷写入冲突（并发幂等键），请重试")
        return {
            "paper": self._paper_dict(paper),
            "session": self._session_dict(session),
            "idempotent": False,
        }

    @staticmethod
    def _validate_idempotency_key(key: Optional[str]) -> Optional[str]:
        """Idempotency-Key 格式校验：可选；去空白后 1-128 位，字母/数字开头，允许 [A-Za-z0-9._:~-]。"""
        if key is None:
            return None
        key = str(key).strip()
        if not key:
            return None
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:~-]{0,127}", key):
            raise ValidationException(
                "Idempotency-Key 格式不合法（1-128 位，字母/数字开头，允许 ._:~-）"
            )
        return key

    @staticmethod
    def _assembly_signature(
        question_bank_id: int,
        knowledge_ids: Optional[List[int]],
        type_needs: Dict[str, int],
        diff_needs: Dict[int, int],
        total_count: int,
    ) -> dict:
        """规范化组卷参数签名（知识升序、计数含 0 键）：幂等比对与 assembly_config 落库共用同一格式。"""
        return {
            "question_bank_id": int(question_bank_id),
            "knowledge_ids": sorted(int(k) for k in (knowledge_ids or [])),
            "question_type_counts": {
                k: int(type_needs.get(k, 0)) for k in sorted(type_needs)
            },
            "difficulty_distribution": {
                DIFFICULTY_CODE_TO_NAME[d]: int(n) for d, n in sorted(diff_needs.items())
            },
            "total_count": int(total_count),
            "selection_strategy": "random",
        }

    @staticmethod
    def _canonicalize_stored_config(cfg: Optional[dict]) -> dict:
        """把 assembly_config（含历史行）归一化为签名可比形式：补全 0 键、知识升序。"""
        cfg = cfg or {}
        type_counts = cfg.get("question_type_counts") or {}
        diff = cfg.get("difficulty_distribution") or {}
        return {
            "question_bank_id": cfg.get("question_bank_id"),
            "knowledge_ids": sorted(int(k) for k in (cfg.get("knowledge_ids") or [])),
            "question_type_counts": {
                k: int(type_counts.get(k, 0))
                for k in ("MULTIPLE_CHOICE", "SHORT_ANSWER", "SINGLE_CHOICE", "TRUE_FALSE")
            },
            "difficulty_distribution": {
                name: int(diff.get(name, 0)) for name in ("easy", "hard", "normal")
            },
            "total_count": int(cfg.get("total_count") or 0),
            "selection_strategy": cfg.get("selection_strategy") or "random",
        }

    def _idempotent_response(self, existing: PracticePaper, signature: dict) -> dict:
        """幂等命中：请求签名与原卷一致 → 返回原卷；不一致 → 40001 幂等冲突（不悄悄返回旧卷）。"""
        stored = self._canonicalize_stored_config(existing.assembly_config)
        incoming = self._canonicalize_stored_config(signature)
        if stored != incoming:
            raise ValidationException("幂等键已用于不同的组卷参数（Idempotency-Key 冲突），请更换幂等键")
        first_session = (
            self.db.query(PracticeSession)
            .filter(PracticeSession.paper_id == existing.id)
            .order_by(PracticeSession.id.asc())
            .first()
        )
        return {
            "paper": self._paper_dict(existing),
            "session": self._session_dict(first_session) if first_session else None,
            "idempotent": True,
        }

    def _select_questions(
        self,
        pool: List[Question],
        type_needs: Dict[str, int],
        diff_needs: Dict[int, int],
        total_count: int,
    ) -> List[int]:
        """随机选题，同时满足题型与难度两个边际分布（贪心：难度维度优先）。"""
        rows = [(q.id, q.question_type, q.difficulty) for q in pool]
        random.shuffle(rows)

        remaining_type = dict(type_needs)
        remaining_diff = dict(diff_needs)
        picked: List[int] = []
        picked_set = set()

        # 先按难度逐档抽取，档内优先取"剩余题型需求最大"的题型
        for diff, diff_need in sorted(diff_needs.items()):
            if diff_need <= 0:
                continue
            taken = 0
            # 每轮按当前剩余题型需求排序，保证题型边际也能被满足
            while taken < diff_need:
                candidates = [
                    (qid, t) for qid, t, d in rows
                    if d == diff and qid not in picked_set and remaining_type.get(t, 0) > 0
                ]
                if not candidates:
                    break
                candidates.sort(key=lambda x: (-remaining_type.get(x[1], 0), x[0]))
                qid, t = candidates[0]
                picked.append(qid)
                picked_set.add(qid)
                remaining_type[t] -= 1
                remaining_diff[diff] -= 1
                taken += 1

        # 兜底：某难度档没抽满时，从其他档的富余题型补齐（保持题型边际）
        if len(picked) < total_count:
            for qid, t, d in rows:
                if len(picked) >= total_count:
                    break
                if qid in picked_set:
                    continue
                if remaining_type.get(t, 0) > 0:
                    picked.append(qid)
                    picked_set.add(qid)
                    remaining_type[t] -= 1
                    remaining_diff[d] = remaining_diff.get(d, 0) - 1

        random.shuffle(picked)  # 题目顺序打乱，快照保存最终顺序
        return picked[:total_count]

    def _build_paper(
        self,
        user_id: int,
        question_bank_id: Optional[int],
        title: str,
        selected_ids: List[int],
        pool_by_id: Dict[int, Question],
        type_needs: Dict[str, int],
        diff_needs: Dict[int, int],
        knowledge_ids: Optional[List[int]],
        idempotency_key: Optional[str],
        total_count: int,
    ) -> Tuple[PracticePaper, List[PracticePaperItem], PracticeSession]:
        # assembly_config 使用与幂等比对相同的规范化签名格式（§6.1：含全部影响组卷结果的参数）
        assembly_config = self._assembly_signature(
            question_bank_id, knowledge_ids, type_needs, diff_needs, total_count
        )

        # 先构建快照，再算确定性哈希（sort_keys + 全量字段）
        snapshot_blobs = []
        items_data = []
        for order, qid in enumerate(selected_ids, start=1):
            question = pool_by_id[qid]
            options = (
                self.db.query(QuestionOption)
                .filter(QuestionOption.question_id == qid)
                .order_by(QuestionOption.sort_order.asc())
                .all()
            )
            knowledge_points = self._knowledge_points_of(qid)
            score = Decimal("5")
            payload = _snapshot_item_payload(question, options, knowledge_points, score)
            snapshot_blobs.append(payload)
            items_data.append((order, question, payload))

        snapshot_hash = hashlib.sha256(
            json.dumps(
                {"snapshot_version": 1, "items": snapshot_blobs, "config": assembly_config},
                sort_keys=True,
                ensure_ascii=False,
                default=str,
            ).encode("utf-8")
        ).hexdigest()

        paper = PracticePaper(
            owner_user_id=user_id,
            source_question_bank_id=question_bank_id,
            title=title,
            snapshot_version=1,
            snapshot_hash=snapshot_hash,
            assembly_config=assembly_config,
            question_count=len(items_data),
            total_score=Decimal("5") * len(items_data),
            status="ready",
            idempotency_key=idempotency_key,
        )
        self.db.add(paper)
        self.db.flush()

        items: List[PracticePaperItem] = []
        for order, question, payload in items_data:
            item = PracticePaperItem(
                paper_id=paper.id,
                source_question_id=question.id,
                sort_order=order,
                question_type=question.question_type,
                difficulty=question.difficulty,
                score=Decimal(str(payload["score"])),
                source_status_at_snapshot=question.status,
                source_content_hash=question.content_hash,
                knowledge_snapshot=payload.get("knowledge_points"),
                question_snapshot=payload,
            )
            self.db.add(item)
            items.append(item)
        self.db.flush()

        now = datetime.utcnow()
        session = PracticeSession(
            app_user_id=user_id,
            paper_id=paper.id,
            mode="practice",
            status="in_progress",
            current_item_order=1,
            total_count=len(items),
            started_at=now,
            last_active_at=now,
        )
        self.db.add(session)
        self.db.flush()

        for item in items:
            self.db.add(PracticeSessionItem(
                session_id=session.id,
                paper_item_id=item.id,
                status="unanswered",
                is_marked=False,
                created_at=now,
                updated_at=now,
            ))
        self.db.flush()
        return paper, items, session

    # ==================== 试卷查询 / 归档 / 再练 ====================

    def list_papers(self, user_id: int, page: int, page_size: int):
        query = (
            self.db.query(PracticePaper)
            .filter(
                PracticePaper.owner_user_id == user_id,
                PracticePaper.deleted_at.is_(None),
            )
            .order_by(PracticePaper.id.desc())
        )
        total = query.count()
        rows = query.offset((page - 1) * page_size).limit(page_size).all()
        items = []
        for p in rows:
            d = self._paper_dict(p)
            last_session = (
                self.db.query(PracticeSession)
                .filter(PracticeSession.paper_id == p.id)
                .order_by(PracticeSession.id.desc())
                .first()
            )
            d["recent_session"] = (
                {
                    "session_id": last_session.id,
                    "status": last_session.status,
                    "answered_count": last_session.answered_count,
                    "total_count": last_session.total_count,
                    "last_active_at": last_session.last_active_at.isoformat()
                    if last_session.last_active_at else None,
                }
                if last_session else None
            )
            items.append(d)
        return items, total

    def get_paper(self, user_id: int, paper_id: int) -> dict:
        paper = self._get_owned_paper(user_id, paper_id)
        items = (
            self.db.query(PracticePaperItem)
            .filter(PracticePaperItem.paper_id == paper_id)
            .order_by(PracticePaperItem.sort_order.asc())
            .all()
        )
        d = self._paper_dict(paper)
        # 未答题目不返回正确答案/解析：这里返回的是"题目面"，敏感字段走白名单投影
        d["items"] = [item_public_projection(i) for i in items]
        return d

    def archive_paper(self, user_id: int, paper_id: int) -> dict:
        paper = self._get_owned_paper(user_id, paper_id)
        if paper.status != "ready":
            return self._paper_dict(paper)  # 幂等：已归档直接返回
        paper.status = "archived"
        paper.archived_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(paper)
        return self._paper_dict(paper)

    def create_session(self, user_id: int, paper_id: int) -> dict:
        paper = self._get_owned_paper(user_id, paper_id)
        if paper.status != "ready":
            raise ValidationException("试卷已归档，不能再发起新的练习；未归档历史练习仍可继续")

        items = (
            self.db.query(PracticePaperItem)
            .filter(PracticePaperItem.paper_id == paper_id)
            .order_by(PracticePaperItem.sort_order.asc())
            .all()
        )
        now = datetime.utcnow()
        session = PracticeSession(
            app_user_id=user_id,
            paper_id=paper.id,
            mode="practice",
            status="in_progress",
            current_item_order=1,
            total_count=len(items),
            started_at=now,
            last_active_at=now,
        )
        self.db.add(session)
        self.db.flush()
        for item in items:
            self.db.add(PracticeSessionItem(
                session_id=session.id,
                paper_item_id=item.id,
                status="unanswered",
                is_marked=False,
                created_at=now,
                updated_at=now,
            ))
        self.db.commit()
        self.db.refresh(session)
        return self._session_dict(session)

    # ==================== 会话查询 / 状态流转 ====================

    def list_sessions(self, user_id: int, status: Optional[str], page: int, page_size: int):
        query = (
            self.db.query(PracticeSession)
            .filter(PracticeSession.app_user_id == user_id)
            .order_by(PracticeSession.id.desc())
        )
        if status:
            query = query.filter(PracticeSession.status == status)
        total = query.count()
        rows = query.offset((page - 1) * page_size).limit(page_size).all()
        return [self._session_dict(s) for s in rows], total

    def get_session_detail(self, user_id: int, session_id: int) -> dict:
        session = self._get_owned_session(user_id, session_id)
        session.last_active_at = datetime.utcnow()
        self.db.commit()

        items = self._session_items_with_paper(session_id)
        result_items = []
        for paper_item, session_item in items:
            # 统一状态化投影（§8）：未提交题不返回 correct_answer/explanation/is_correct
            proj = item_projection_for_state(paper_item, session_item, session.status)
            if "correct_answer" not in proj:
                proj["draft_answer"] = (session_item.draft_answer or {}).get("answer") if session_item else None
            proj["status"] = session_item.status if session_item else "unanswered"
            proj["is_marked"] = bool(session_item.is_marked) if session_item else False
            result_items.append(proj)

        paper = self.db.query(PracticePaper).get(session.paper_id)
        return {
            "session": self._session_dict(session),
            "paper": self._paper_dict(paper),
            "items": result_items,
            "progress": self._progress_dict(session),
        }

    def resume_session(self, user_id: int, session_id: int) -> dict:
        session = self._get_owned_session(user_id, session_id)
        if session.status == "completed":
            raise ValidationException("已完成的会话不能继续作答；可对同一试卷发起新的练习")
        if session.status == "abandoned":
            raise ValidationException("已放弃的会话不能继续作答；可对同一试卷发起新的练习")
        session.last_active_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(session)
        return self._session_dict(session)

    def complete_session(self, user_id: int, session_id: int) -> dict:
        session = self._get_owned_session(user_id, session_id)
        if session.status == "completed":
            return self._session_dict(session)  # 幂等：重复完成返回原状态
        if session.status == "abandoned":
            raise ValidationException("已放弃的会话不能标记完成")

        now = datetime.utcnow()
        session.status = "completed"
        session.completed_at = now
        session.last_active_at = now
        if session.started_at:
            session.duration_ms = int((now - session.started_at).total_seconds() * 1000)
        self._recompute_session_counters(session)
        self.db.commit()
        self.db.refresh(session)
        return self._session_dict(session)

    def abandon_session(self, user_id: int, session_id: int) -> dict:
        session = self._get_owned_session(user_id, session_id)
        if session.status == "completed":
            raise ValidationException("已完成的会话不能放弃；如需重新练习请发起新的会话")
        if session.status == "abandoned":
            return self._session_dict(session)  # 幂等
        now = datetime.utcnow()
        session.status = "abandoned"
        session.abandoned_at = now
        session.last_active_at = now
        self._recompute_session_counters(session)
        self.db.commit()
        self.db.refresh(session)
        return self._session_dict(session)

    def session_result(self, user_id: int, session_id: int) -> dict:
        """会话结果/回顾（§8）：completed 全量回顾；in_progress/abandoned 未提交题不返回答案。"""
        session = self._get_owned_session(user_id, session_id)
        items = self._session_items_with_paper(session_id)
        rows = []
        total_score = Decimal("0")
        earned_score = Decimal("0")
        for paper_item, session_item in items:
            proj = item_projection_for_state(paper_item, session_item, session.status)
            proj["status"] = session_item.status if session_item else "unanswered"
            rows.append(proj)
            total_score += Decimal(str(paper_item.score))
            if session_item and session_item.latest_is_correct:
                earned_score += Decimal(str(paper_item.score))
        return {
            "session": self._session_dict(session),
            "items": rows,
            "summary": {
                "total_count": session.total_count,
                "answered_count": session.answered_count,
                "correct_count": session.correct_count,
                "incorrect_count": session.incorrect_count,
                "ungraded_count": session.ungraded_count,
                "total_score": float(total_score),
                "earned_score": float(earned_score),
            },
        }

    def session_answers(self, user_id: int, session_id: int) -> dict:
        """会话答题记录列表（按提交时间排序，题面来自快照）。"""
        self._get_owned_session(user_id, session_id)
        records = (
            self.db.query(QuestionAnswerRecord)
            .filter(QuestionAnswerRecord.practice_session_id == session_id)
            .order_by(
                QuestionAnswerRecord.created_at.asc(),
                QuestionAnswerRecord.id.asc(),
            )
            .all()
        )
        return {
            "session_id": session_id,
            "answers": [
                {
                    "id": r.id,
                    "question_id": r.question_id,
                    "practice_paper_item_id": r.practice_paper_item_id,
                    "user_answer": r.user_answer,
                    "is_correct": (
                        bool(r.is_correct) if r.is_correct is not None else None
                    ),
                    "grading_status": r.grading_status,
                    "score": float(r.score) if r.score is not None else None,
                    "time_spent_ms": r.time_spent_ms,
                    "idempotency_key": r.idempotency_key,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in records
            ],
        }

    # ==================== 草稿 / 标记 / 进度 ====================

    def save_draft(self, user_id: int, session_id: int, paper_item_id: int, answer: Any) -> dict:
        """保存草稿（§7）：只写 draft_answer，不建答题记录、不进统计；草稿值按题型 JSON 值校验类型。"""
        session = self._get_owned_session(user_id, session_id)
        if session.status != "in_progress":
            raise ValidationException("会话不是进行中，不能保存草稿")
        session_item = self._get_session_item(session_id, paper_item_id)
        paper_item = self.db.query(PracticePaperItem).get(paper_item_id)
        if answer is not None:
            # 校验草稿值符合题型（允许空草稿=清除）；非法类型/未知选项键报参数错误
            coerce_answer(paper_item.question_snapshot or {}, answer)
        if session_item.status != "answered":
            session_item.status = "draft_saved"
        session_item.draft_answer = {"answer": answer}
        session_item.updated_at = datetime.utcnow()
        session.last_active_at = datetime.utcnow()
        self.db.commit()
        return {
            "session_id": session_id,
            "paper_item_id": paper_item_id,
            "status": session_item.status,
            "draft_answer": session_item.draft_answer,
        }

    def mark_item(self, user_id: int, session_id: int, paper_item_id: int, is_marked: bool) -> dict:
        session = self._get_owned_session(user_id, session_id)
        if session.status != "in_progress":
            raise ValidationException("会话不是进行中，不能修改标记")
        session_item = self._get_session_item(session_id, paper_item_id)
        session_item.is_marked = bool(is_marked)
        session_item.updated_at = datetime.utcnow()
        self.db.commit()
        return {"paper_item_id": paper_item_id, "is_marked": session_item.is_marked}

    def update_progress(self, user_id: int, session_id: int, current_item_order: int) -> dict:
        session = self._get_owned_session(user_id, session_id)
        if session.status != "in_progress":
            raise ValidationException("会话不是进行中，不能更新进度")
        if not (1 <= current_item_order <= max(1, session.total_count)):
            raise ValidationException(f"current_item_order 必须在 1-{session.total_count} 之间")
        session.current_item_order = current_item_order
        session.last_active_at = datetime.utcnow()
        self.db.commit()
        return {"session_id": session_id, "current_item_order": current_item_order}

    # ==================== 提交判分 ====================

    def submit_answer(
        self,
        user_id: int,
        session_id: int,
        paper_item_id: int,
        answer: Any,
        idempotency_key: str,
        time_spent_ms: Optional[int] = None,
    ) -> dict:
        """提交答案（§9）：answer 按题型 JSON 值；判分只读 question_snapshot 严禁读现题；
        同 key 同内容返回原记录、同 key 异内容 40001 幂等冲突、新 key=新尝试追加记录。"""
        session = self._get_owned_session(user_id, session_id)
        if session.status != "in_progress":
            raise ValidationException("会话不是进行中，不能提交答案")
        session_item = self._get_session_item(session_id, paper_item_id)
        paper_item = self.db.query(PracticePaperItem).get(paper_item_id)

        snapshot = paper_item.question_snapshot or {}

        # 判分：以快照标准答案为准（含答案按题型规范化与合法性校验）
        verdict = judge(snapshot, answer)
        normalized = verdict["user_answer_text"]

        # 幂等：同 key 同请求返回原记录；同 key 不同请求明确冲突
        existing = (
            self.db.query(QuestionAnswerRecord)
            .filter(
                QuestionAnswerRecord.app_user_id == user_id,
                QuestionAnswerRecord.idempotency_key == idempotency_key,
            )
            .first()
        )
        if existing:
            same_target = existing.practice_paper_item_id == paper_item_id
            same_payload = (existing.user_answer or "") == normalized
            if same_target and same_payload:
                return self._submit_response(session, session_item, paper_item, existing, idempotent=True)
            raise ValidationException("幂等键已用于不同的提交内容，请更换 idempotency_key")

        now = datetime.utcnow()
        record = QuestionAnswerRecord(
            question_id=paper_item.source_question_id or 0,
            user_id=user_id,  # 历史兼容列（NOT NULL），与 app_user_id 同值
            app_user_id=user_id,
            practice_paper_id=session.paper_id,
            practice_paper_item_id=paper_item_id,
            practice_session_id=session_id,
            user_answer=verdict["user_answer_text"],
            is_correct=1 if verdict["is_correct"] else (0 if verdict["is_correct"] is False else None),
            grading_status=verdict["grading_status"],
            score=verdict["score"],
            time_spent_ms=time_spent_ms,
            idempotency_key=idempotency_key,
            created_at=now,
        )
        self.db.add(record)
        self.db.flush()

        # 更新会话题目指针（首次提交时间不被覆盖）
        session_item.status = "answered"
        session_item.draft_answer = {"answer": answer}
        session_item.latest_answer_record_id = record.id
        session_item.latest_is_correct = (
            bool(verdict["is_correct"]) if verdict["is_correct"] is not None else None
        )
        session_item.latest_grading_status = verdict["grading_status"]
        if session_item.first_submitted_at is None:
            session_item.first_submitted_at = now
        session_item.last_submitted_at = now
        session_item.updated_at = now

        session.last_active_at = now
        self._recompute_session_counters(session)
        self.db.commit()

        return self._submit_response(session, session_item, paper_item, record, idempotent=False)

    def _submit_response(self, session, session_item, paper_item, record, idempotent: bool) -> dict:
        snap = paper_item.question_snapshot or {}
        return {
            "answer_record_id": record.id,
            "idempotent": idempotent,
            "paper_item_id": paper_item.id,
            "question_id": paper_item.source_question_id,
            "is_correct": (
                bool(record.is_correct) if record.is_correct is not None else None
            ),
            "grading_status": record.grading_status,
            "score": float(record.score) if record.score is not None else None,
            # 仅提交后返回正确答案与解析（提交前接口一律不返回）
            "correct_answer": snap.get("correct_answer"),
            "explanation": snap.get("explanation"),
            "session_progress": self._progress_dict(session),
        }

    def _recompute_session_counters(self, session: PracticeSession) -> None:
        """会话统计统一重算（幂等，只按 item 最新状态聚合）。"""
        items = (
            self.db.query(PracticeSessionItem)
            .filter(PracticeSessionItem.session_id == session.id)
            .all()
        )
        answered = sum(1 for i in items if i.status == "answered")
        correct = sum(1 for i in items if i.status == "answered" and i.latest_is_correct is True)
        incorrect = sum(1 for i in items if i.status == "answered" and i.latest_is_correct is False)
        ungraded = sum(
            1 for i in items
            if i.status == "answered" and i.latest_grading_status == "ungraded"
        )
        session.answered_count = answered
        session.correct_count = correct
        session.incorrect_count = incorrect
        session.ungraded_count = ungraded

    # ==================== 内部工具 ====================

    @staticmethod
    def _normalize_counts(counts: Optional[Dict[str, int]]) -> Dict[str, int]:
        result = {}
        for raw_type, raw_count in (counts or {}).items():
            q_type = str(raw_type or "").strip().upper()
            if q_type not in VALID_TYPES:
                raise ValidationException(f"不支持的题型: {raw_type}")
            try:
                n = int(raw_count)
            except (TypeError, ValueError):
                raise ValidationException(f"题型数量必须为整数: {raw_type}")
            if n < 0:
                raise ValidationException(f"题型数量不能为负: {raw_type}")
            if n > 0:
                result[q_type] = n
        return result

    @staticmethod
    def _normalize_difficulty(dist: Optional[Dict[str, int]]) -> Dict[int, int]:
        result = {}
        for raw_name, raw_count in (dist or {}).items():
            name = str(raw_name or "").strip().lower()
            if name not in DIFFICULTY_NAME_TO_CODE:
                raise ValidationException(f"不支持的难度: {raw_name}")
            try:
                n = int(raw_count)
            except (TypeError, ValueError):
                raise ValidationException(f"难度数量必须为整数: {raw_name}")
            if n < 0:
                raise ValidationException(f"难度数量不能为负: {raw_name}")
            code = DIFFICULTY_NAME_TO_CODE[name]
            result[code] = result.get(code, 0) + n
        return result

    def _knowledge_points_of(self, question_id: int) -> List[dict]:
        rows = (
            self.db.query(QuestionKnowledge, Knowledge)
            .join(Knowledge, Knowledge.id == QuestionKnowledge.knowledge_id)
            .filter(QuestionKnowledge.question_id == question_id)
            .all()
        )
        return [
            {
                "knowledge_id": qk.knowledge_id,
                "name": k.name,
                "difficulty": k.difficulty,
                "importance_level": k.importance_level,
            }
            for qk, k in rows
        ]

    def _get_owned_paper(self, user_id: int, paper_id: int) -> PracticePaper:
        paper = (
            self.db.query(PracticePaper)
            .filter(
                PracticePaper.id == paper_id,
                PracticePaper.owner_user_id == user_id,
                PracticePaper.deleted_at.is_(None),
            )
            .first()
        )
        if paper is None:
            raise ResourceNotFoundException("试卷不存在")
        return paper

    def _get_owned_session(self, user_id: int, session_id: int) -> PracticeSession:
        session = (
            self.db.query(PracticeSession)
            .filter(
                PracticeSession.id == session_id,
                PracticeSession.app_user_id == user_id,
            )
            .first()
        )
        if session is None:
            raise ResourceNotFoundException("练习会话不存在")
        return session

    def _get_session_item(self, session_id: int, paper_item_id: int) -> PracticeSessionItem:
        session_item = (
            self.db.query(PracticeSessionItem)
            .filter(
                PracticeSessionItem.session_id == session_id,
                PracticeSessionItem.paper_item_id == paper_item_id,
            )
            .first()
        )
        if session_item is None:
            raise ResourceNotFoundException("该题目不属于本次练习会话")
        return session_item

    def _session_items_with_paper(self, session_id: int):
        rows = (
            self.db.query(PracticePaperItem, PracticeSessionItem)
            .join(
                PracticeSessionItem,
                PracticeSessionItem.paper_item_id == PracticePaperItem.id,
            )
            .filter(PracticeSessionItem.session_id == session_id)
            .order_by(PracticePaperItem.sort_order.asc())
            .all()
        )
        return rows

    @staticmethod
    def _paper_dict(paper: PracticePaper) -> dict:
        return {
            "paper_id": paper.id,
            "title": paper.title,
            "question_count": paper.question_count,
            "total_score": float(paper.total_score),
            "status": paper.status,
            "source_question_bank_id": paper.source_question_bank_id,
            "assembly_config": paper.assembly_config,
            "snapshot_version": paper.snapshot_version,
            "snapshot_hash": paper.snapshot_hash,
            "created_at": paper.created_at.isoformat() if paper.created_at else None,
            "archived_at": paper.archived_at.isoformat() if paper.archived_at else None,
        }

    @staticmethod
    def _session_dict(session: Optional[PracticeSession]) -> Optional[dict]:
        if session is None:
            return None
        return {
            "session_id": session.id,
            "paper_id": session.paper_id,
            "mode": session.mode,
            "status": session.status,
            "current_item_order": session.current_item_order,
            "total_count": session.total_count,
            "answered_count": session.answered_count,
            "correct_count": session.correct_count,
            "incorrect_count": session.incorrect_count,
            "ungraded_count": session.ungraded_count,
            "started_at": session.started_at.isoformat() if session.started_at else None,
            "last_active_at": session.last_active_at.isoformat() if session.last_active_at else None,
            "completed_at": session.completed_at.isoformat() if session.completed_at else None,
            "abandoned_at": session.abandoned_at.isoformat() if session.abandoned_at else None,
            "duration_ms": session.duration_ms,
        }

    @staticmethod
    def _progress_dict(session: PracticeSession) -> dict:
        return {
            "session_id": session.id,
            "status": session.status,
            "total_count": session.total_count,
            "answered_count": session.answered_count,
            "correct_count": session.correct_count,
            "incorrect_count": session.incorrect_count,
            "ungraded_count": session.ungraded_count,
            "current_item_order": session.current_item_order,
        }
