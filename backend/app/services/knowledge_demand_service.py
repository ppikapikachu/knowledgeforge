"""知识点需求评估与分配服务。

纯业务服务，不依赖 LLM，可被管理员主动出题和未来自动补题复用。
"""

import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.knowledge import Knowledge
from app.models.knowledge_base import KnowledgeBase
from app.models.question import Question
from app.models.question_answer_record import QuestionAnswerRecord
from app.models.question_bank_knowledge_base import QuestionBankKnowledgeBase
from app.models.question_generation_task import QuestionGenerationTask
from app.models.question_knowledge import QuestionKnowledge

# 重要程度常量（前后端必须一致）
IMPORTANCE_LEVELS = [
    {"value": "core", "label": "核心必考", "description": "基础主干、关键原理、必要前置概念", "score": 1.0},
    {"value": "important", "label": "重点掌握", "description": "重要机制、常见实践和关键限制", "score": 0.75},
    {"value": "normal", "label": "常见考点", "description": "常规且有学习价值的知识点", "score": 0.5},
    {"value": "supplementary", "label": "扩展了解", "description": "低频细节、边缘用法和补充内容", "score": 0.25},
]
IMPORTANCE_SCORE_MAP = {item["value"]: item["score"] for item in IMPORTANCE_LEVELS}
IMPORTANCE_LABEL_MAP = {item["value"]: item["label"] for item in IMPORTANCE_LEVELS}


class KnowledgePointDemandService:
    """知识点需求评估与分配。"""

    def __init__(self, db: Session):
        self.db = db

    def evaluate(
        self,
        question_bank_id: int,
        question_type: str,
        difficulty: int,
        policy: dict,
        exclude_task_id: Optional[int] = None,
    ) -> List[dict]:
        """查询候选知识点统计并计算需求指标。"""
        # 获取候选知识点：题库关联的知识库下，状态有效
        kb_ids = self._get_knowledge_base_ids(question_bank_id)
        if not kb_ids:
            return []

        candidates = (
            self.db.query(Knowledge)
            .filter(
                Knowledge.knowledge_base_id.in_(kb_ids),
                Knowledge.status == 1,
            )
            .all()
        )
        if not candidates:
            return []

        candidate_ids = [k.id for k in candidates]

        # 批量统计库存
        published_counts = self._get_question_counts(candidate_ids, "published")
        pending_counts = self._get_question_counts(candidate_ids, "pending_review")
        reserved_counts = self._get_reserved_counts(candidate_ids, exclude_task_id)

        # 批量统计使用数据
        usage_window = policy.get("usage_window_days", 30)
        since = datetime.utcnow() - timedelta(days=usage_window)
        recent_stats = self._get_recent_usage(candidate_ids, since)

        # 计算需求指标
        target_stock = policy.get("target_stock", 20)
        stock_weight = policy.get("stock_weight", 50)
        usage_weight = policy.get("usage_weight", 30)
        importance_weight = policy.get("importance_weight", 20)
        answers_per_target = policy.get("recent_answers_per_question_target", 3)
        usage_extra_ratio = policy.get("usage_extra_ratio", 0.5)
        max_per_knowledge = policy.get("max_per_knowledge_per_task", 10)
        min_demand_score = policy.get("min_demand_score", 0.15)

        evaluations = []
        for k in candidates:
            pid = k.id
            published = published_counts.get(pid, 0)
            pending = pending_counts.get(pid, 0)
            reserved = reserved_counts.get(pid, 0)
            committed = published + pending + reserved

            recent_used = recent_stats.get(pid, {}).get("used_questions", 0)
            recent_answers = recent_stats.get(pid, {}).get("answers", 0)

            # stock_score
            stock_score = max(0.0, min(1.0, (target_stock - committed) / max(target_stock, 1)))

            # usage_score
            recent_coverage = min(1.0, recent_used / max(published, 1))
            recent_intensity = min(1.0, recent_answers / max(published * answers_per_target, 1))
            usage_score = 0.5 * recent_coverage + 0.5 * recent_intensity

            # importance_score
            importance_score = IMPORTANCE_SCORE_MAP.get(k.importance_level, 0.5)

            # demand_score
            demand_score = (
                stock_score * stock_weight / 100
                + usage_score * usage_weight / 100
                + importance_score * importance_weight / 100
            )
            demand_score = round(max(0.0, min(1.0, demand_score)), 4)

            # demand_count
            base_gap = max(target_stock - committed, 0)
            usage_extra = math.ceil(target_stock * usage_score * usage_extra_ratio)
            demand_count = min(max(base_gap, usage_extra), max_per_knowledge)

            # reason codes
            reason_codes = []
            if stock_score > 0.3:
                reason_codes.append("LOW_STOCK")
            if usage_score > 0.5:
                reason_codes.append("HIGH_USAGE")
            if importance_score >= 0.75:
                reason_codes.append("HIGH_IMPORTANCE")

            reason_parts = []
            if "LOW_STOCK" in reason_codes:
                reason_parts.append("可用库存偏少")
            if "HIGH_USAGE" in reason_codes:
                reason_parts.append("近期使用频繁")
            if "HIGH_IMPORTANCE" in reason_codes:
                reason_parts.append(f"重要程度为{IMPORTANCE_LABEL_MAP.get(k.importance_level, '未知')}")

            evaluations.append({
                "knowledge_id": pid,
                "knowledge_name": k.name,
                "knowledge_base_id": k.knowledge_base_id,
                "importance_level": k.importance_level,
                "importance_label": IMPORTANCE_LABEL_MAP.get(k.importance_level, "未知"),
                "published_count": published,
                "pending_review_count": pending,
                "reserved_count": reserved,
                "recent_used_question_count": recent_used,
                "recent_answer_count": recent_answers,
                "stock_score": round(stock_score, 4),
                "usage_score": round(usage_score, 4),
                "importance_score": round(importance_score, 4),
                "demand_score": demand_score,
                "demand_count": demand_count,
                "reason_codes": reason_codes,
                "reason_summary": "，".join(reason_parts) if reason_parts else "正常需求",
            })

        # 过滤低需求
        evaluations = [e for e in evaluations if e["demand_score"] >= min_demand_score]
        return evaluations

    def allocate(
        self,
        evaluations: List[dict],
        requested_count: int,
        policy: dict,
    ) -> Tuple[List[dict], int, int, List[str]]:
        """将总题量分配给多个知识点。返回 (allocations, allocatable_count, unallocated_count, warnings)。"""
        max_per_knowledge = policy.get("max_per_knowledge_per_task", 10)
        warnings = []

        if not evaluations:
            return [], 0, requested_count, ["无候选知识点"]

        # 过滤有需求的
        active = [e for e in evaluations if e["demand_count"] > 0]
        if not active:
            return [], 0, requested_count, ["所有候选知识点需求量为 0"]

        total_capacity = sum(min(e["demand_count"], max_per_knowledge) for e in active)
        allocatable = min(requested_count, total_capacity)

        if allocatable < requested_count:
            warnings.append(f"当前候选知识点最多可分配 {allocatable} 道，少于目标 {requested_count} 道")

        # 按 demand_score 加权分配
        total_score = sum(e["demand_score"] for e in active)
        if total_score == 0:
            total_score = len(active)
            for e in active:
                e["_weight"] = 1.0
        else:
            for e in active:
                e["_weight"] = e["demand_score"]

        # 初始分配（最大余数法）
        raw_allocations = []
        for e in active:
            cap = min(e["demand_count"], max_per_knowledge)
            raw = allocatable * (e["_weight"] / total_score)
            floor_val = min(int(raw), cap)
            raw_allocations.append({
                "eval": e,
                "cap": cap,
                "floor": floor_val,
                "frac": raw - int(raw),
                "remaining": cap - floor_val,
            })

        allocated = sum(r["floor"] for r in raw_allocations)
        remainder = allocatable - allocated

        # 按小数部分降序分配剩余
        raw_allocations.sort(key=lambda r: r["frac"], reverse=True)
        for r in raw_allocations:
            if remainder <= 0:
                break
            if r["remaining"] > 0:
                r["floor"] += 1
                r["remaining"] -= 1
                remainder -= 1

        # 构建结果
        allocations = []
        for r in raw_allocations:
            e = r["eval"]
            allocated_count = r["floor"]
            if allocated_count <= 0:
                continue
            allocations.append({
                **e,
                "allocated_count": allocated_count,
            })

        # 排序：allocated_count 降序，demand_score 降序
        allocations.sort(key=lambda x: (x["allocated_count"], x["demand_score"]), reverse=True)

        unallocated = requested_count - sum(a["allocated_count"] for a in allocations)
        return allocations, allocatable, unallocated, warnings

    def preview(
        self,
        question_bank_id: int,
        question_type: str,
        difficulty: int,
        count: int,
        policy: dict,
    ) -> dict:
        """返回可解释的预览结果，不写数据库、不调用 LLM。"""
        kb_ids = self._get_knowledge_base_ids(question_bank_id)
        if not kb_ids:
            return {
                "question_bank_id": question_bank_id,
                "allocation_mode": "auto",
                "requested_count": count,
                "allocatable_count": 0,
                "unallocated_count": count,
                "is_fully_allocatable": False,
                "policy_version": policy.get("version"),
                "summary": {"candidate_knowledge_count": 0, "selected_knowledge_count": 0},
                "allocations": [],
                "warnings": ["QUESTION_BANK_SCOPE_NOT_CONFIGURED: 题库未关联知识库，请先配置知识范围"],
            }

        evaluations = self.evaluate(question_bank_id, question_type, difficulty, policy)

        # 区分不同零候选场景
        raw_candidates = self._get_raw_candidates(kb_ids)
        min_demand_score = policy.get("min_demand_score", 0.15)
        pre_filter_count = len(raw_candidates)
        post_filter_count = len(evaluations)

        if not raw_candidates:
            warnings_prefix = ["NO_KNOWLEDGE_IN_SCOPE: 关联知识库中没有有效知识点"]
            return {
                "question_bank_id": question_bank_id,
                "allocation_mode": "auto",
                "requested_count": count,
                "allocatable_count": 0,
                "unallocated_count": count,
                "is_fully_allocatable": False,
                "policy_version": policy.get("version"),
                "summary": {"candidate_knowledge_count": 0, "selected_knowledge_count": 0},
                "allocations": [],
                "warnings": warnings_prefix,
            }

        if pre_filter_count > 0 and post_filter_count == 0:
            warnings_prefix = [
                f"ALL_BELOW_MIN_DEMAND: 共 {pre_filter_count} 个知识点，"
                f"但需求分均低于阈值 {min_demand_score}"
            ]
        else:
            warnings_prefix = []

        allocations, allocatable, unallocated, alloc_warnings = self.allocate(evaluations, count, policy)

        # 补充 knowledge_base_name
        kb_names = self._get_knowledge_base_names(kb_ids)
        for a in allocations:
            a["knowledge_base_name"] = kb_names.get(a["knowledge_base_id"], "未知")

        all_warnings = warnings_prefix + alloc_warnings

        return {
            "question_bank_id": question_bank_id,
            "allocation_mode": "auto",
            "requested_count": count,
            "allocatable_count": allocatable,
            "unallocated_count": unallocated,
            "is_fully_allocatable": unallocated == 0,
            "policy_version": policy.get("version"),
            "summary": {
                "candidate_knowledge_count": post_filter_count,
                "selected_knowledge_count": len(allocations),
            },
            "allocations": allocations,
            "warnings": all_warnings,
        }

    # --- 内部辅助方法 ---

    def _get_raw_candidates(self, kb_ids: List[int]) -> List[Knowledge]:
        """获取未经过需求过滤的候选知识点列表。"""
        return (
            self.db.query(Knowledge)
            .filter(
                Knowledge.knowledge_base_id.in_(kb_ids),
                Knowledge.status == 1,
            )
            .all()
        )

    def _get_knowledge_base_ids(self, question_bank_id: int) -> List[int]:
        rows = (
            self.db.query(QuestionBankKnowledgeBase.knowledge_base_id)
            .filter(QuestionBankKnowledgeBase.question_bank_id == question_bank_id)
            .all()
        )
        return [r[0] for r in rows]

    def _get_knowledge_base_names(self, kb_ids: List[int]) -> Dict[int, str]:
        rows = (
            self.db.query(KnowledgeBase.id, KnowledgeBase.name)
            .filter(KnowledgeBase.id.in_(kb_ids))
            .all()
        )
        return {r[0]: r[1] for r in rows}

    def _get_question_counts(self, knowledge_ids: List[int], status: str) -> Dict[int, int]:
        """统计每个知识点的题目数。"""
        from app.models.question_knowledge import QuestionKnowledge
        rows = (
            self.db.query(QuestionKnowledge.knowledge_id, func.count(QuestionKnowledge.id))
            .join(Question, Question.id == QuestionKnowledge.question_id)
            .filter(
                QuestionKnowledge.knowledge_id.in_(knowledge_ids),
                Question.status == status,
            )
            .group_by(QuestionKnowledge.knowledge_id)
            .all()
        )
        return {r[0]: r[1] for r in rows}

    def _get_reserved_counts(self, knowledge_ids: List[int], exclude_task_id: Optional[int]) -> Dict[int, int]:
        """统计 pending/running 任务已分配的预留量。"""
        # 从 allocation_plan JSON 中聚合
        query = (
            self.db.query(QuestionGenerationTask.allocation_plan)
            .filter(
                QuestionGenerationTask.status.in_(["pending", "running"]),
                QuestionGenerationTask.allocation_plan.isnot(None),
            )
        )
        if exclude_task_id:
            query = query.filter(QuestionGenerationTask.id != exclude_task_id)

        reserved = {kid: 0 for kid in knowledge_ids}
        for (plan,) in query.all():
            if not plan or "items" not in plan:
                continue
            for item in plan["items"]:
                kid = item.get("knowledge_id")
                if kid in reserved:
                    reserved[kid] += item.get("planned_count", 0)
        return reserved

    def _get_recent_usage(self, knowledge_ids: List[int], since: datetime) -> Dict[int, dict]:
        """统计近期使用数据。"""
        # recent_answer_count: 最近窗口内的答题记录数（通过 question_knowledge 关联）
        answer_rows = (
            self.db.query(
                QuestionKnowledge.knowledge_id,
                func.count(QuestionAnswerRecord.id),
                func.count(func.distinct(QuestionAnswerRecord.question_id)),
            )
            .join(QuestionAnswerRecord, QuestionAnswerRecord.question_id == QuestionKnowledge.question_id)
            .filter(
                QuestionKnowledge.knowledge_id.in_(knowledge_ids),
                QuestionAnswerRecord.created_at >= since,
            )
            .group_by(QuestionKnowledge.knowledge_id)
            .all()
        )
        return {
            r[0]: {"answers": r[1], "used_questions": r[2]}
            for r in answer_rows
        }
