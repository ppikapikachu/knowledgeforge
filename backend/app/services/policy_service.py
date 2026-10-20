"""出题策略管理服务。"""

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.core.exceptions import ValidationException, ResourceNotFoundException
from app.models.question_generation_policy import QuestionGenerationPolicy


class PolicyService:
    """出题策略管理。"""

    def __init__(self, db: Session):
        self.db = db

    def get_effective_policy(self, question_bank_id: Optional[int] = None) -> dict:
        """获取生效策略。题库级优先，否则全局。"""
        if question_bank_id is not None:
            override = (
                self.db.query(QuestionGenerationPolicy)
                .filter(QuestionGenerationPolicy.question_bank_id == question_bank_id)
                .first()
            )
            if override:
                return {
                    "question_bank_id": question_bank_id,
                    "source": "question_bank_override",
                    "policy": self._to_dict(override),
                }

        # 全局策略
        global_policy = (
            self.db.query(QuestionGenerationPolicy)
            .filter(QuestionGenerationPolicy.question_bank_id.is_(None))
            .first()
        )
        if not global_policy:
            # 创建默认全局策略
            global_policy = QuestionGenerationPolicy(question_bank_id=None)
            self.db.add(global_policy)
            self.db.commit()
            self.db.refresh(global_policy)

        return {
            "question_bank_id": question_bank_id,
            "source": "global_default",
            "policy": self._to_dict(global_policy),
        }

    def save_global_policy(self, data: dict) -> dict:
        """保存全局策略。"""
        self._validate_weights(data)
        policy = (
            self.db.query(QuestionGenerationPolicy)
            .filter(QuestionGenerationPolicy.question_bank_id.is_(None))
            .first()
        )
        if not policy:
            policy = QuestionGenerationPolicy(question_bank_id=None)
            self.db.add(policy)

        self._apply_fields(policy, data)
        policy.version = (policy.version or 0) + 1
        self.db.commit()
        self.db.refresh(policy)
        return self._to_dict(policy)

    def save_question_bank_policy(self, question_bank_id: int, data: dict) -> dict:
        """保存题库级策略。"""
        self._validate_weights(data)
        policy = (
            self.db.query(QuestionGenerationPolicy)
            .filter(QuestionGenerationPolicy.question_bank_id == question_bank_id)
            .first()
        )
        if not policy:
            policy = QuestionGenerationPolicy(question_bank_id=question_bank_id)
            self.db.add(policy)

        self._apply_fields(policy, data)
        policy.version = (policy.version or 0) + 1
        self.db.commit()
        self.db.refresh(policy)
        return self._to_dict(policy)

    def delete_question_bank_policy(self, question_bank_id: int) -> bool:
        """删除题库级覆盖策略。"""
        policy = (
            self.db.query(QuestionGenerationPolicy)
            .filter(QuestionGenerationPolicy.question_bank_id == question_bank_id)
            .first()
        )
        if not policy:
            raise ResourceNotFoundException("题库级策略不存在")
        self.db.delete(policy)
        self.db.commit()
        return True

    def _validate_weights(self, data: dict):
        total = data.get("stock_weight", 50) + data.get("usage_weight", 30) + data.get("importance_weight", 20)
        if total != 100:
            raise ValidationException(f"INVALID_POLICY_WEIGHTS: 权重合计必须为 100，当前为 {total}")

    def _apply_fields(self, policy: QuestionGenerationPolicy, data: dict):
        for key in [
            "stock_weight", "usage_weight", "importance_weight",
            "target_stock", "usage_window_days", "recent_answers_per_question_target",
            "usage_extra_ratio", "max_per_knowledge_per_task", "min_demand_score",
        ]:
            if key in data:
                setattr(policy, key, data[key])
        if "is_enabled" in data:
            policy.is_enabled = 1 if data["is_enabled"] else 0

    def _to_dict(self, policy: QuestionGenerationPolicy) -> dict:
        return {
            "stock_weight": policy.stock_weight,
            "usage_weight": policy.usage_weight,
            "importance_weight": policy.importance_weight,
            "target_stock": policy.target_stock,
            "usage_window_days": policy.usage_window_days,
            "recent_answers_per_question_target": policy.recent_answers_per_question_target,
            "usage_extra_ratio": policy.usage_extra_ratio,
            "max_per_knowledge_per_task": policy.max_per_knowledge_per_task,
            "min_demand_score": policy.min_demand_score,
            "is_enabled": bool(policy.is_enabled),
            "version": policy.version,
            "updated_at": policy.updated_at.isoformat() if policy.updated_at else None,
        }
