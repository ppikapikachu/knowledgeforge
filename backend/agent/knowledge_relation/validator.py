"""关系判断结果的确定性校验模块。

LLM 输出后必须经过普通 Python 代码校验，不能完全信任模型输出。
"""

import logging
from typing import List, Optional, Tuple

from agent.knowledge_relation.schemas import (
    KnowledgeRelationJudgement,
)

logger = logging.getLogger(__name__)

VALID_RELATION_TYPES = {"prerequisite", "related", "extension", "contrast"}


class RelationValidator:
    """关系判断结果校验器。"""

    def validate_and_fix(
        self,
        judgements: List[KnowledgeRelationJudgement],
        source_id: int,
        valid_candidate_ids: set,
    ) -> Tuple[List[KnowledgeRelationJudgement], List[str]]:
        """校验并修正 LLM 输出的关系判定结果。

        Args:
            judgements: LLM 输出的判定列表
            source_id: 锚点知识点 ID
            valid_candidate_ids: 有效的候选 ID 集合

        Returns:
            (有效判定列表, 错误信息列表)
        """
        valid = []
        errors = []
        seen_candidate_ids = set()

        for j in judgements:
            try:
                fixed = self._validate_single(j, source_id, valid_candidate_ids)

                # 去重：同一候选只评估一次
                if fixed.candidate_knowledge_id in seen_candidate_ids:
                    errors.append(
                        f"重复候选 {fixed.candidate_knowledge_id}，已跳过"
                    )
                    continue

                seen_candidate_ids.add(fixed.candidate_knowledge_id)
                valid.append(fixed)

            except ValueError as e:
                errors.append(str(e))

        return valid, errors

    def _validate_single(
        self,
        j: KnowledgeRelationJudgement,
        source_id: int,
        valid_candidate_ids: set,
    ) -> KnowledgeRelationJudgement:
        """校验单条判定结果，必要时修正。

        Raises ValueError 如果无法修正。
        """
        # NO_RELATION：清空关系字段
        if j.decision == "NO_RELATION":
            return KnowledgeRelationJudgement(
                candidate_knowledge_id=j.candidate_knowledge_id,
                decision="NO_RELATION",
                relation_type=None,
                from_knowledge_id=None,
                to_knowledge_id=None,
                confidence=j.confidence,
                reason=j.reason,
            )

        # RELATION 校验
        if j.relation_type not in VALID_RELATION_TYPES:
            raise ValueError(
                f"候选 {j.candidate_knowledge_id}: "
                f"非法 relation_type '{j.relation_type}'"
            )

        # 候选 ID 必须在有效集合中
        if j.candidate_knowledge_id not in valid_candidate_ids:
            raise ValueError(
                f"候选 {j.candidate_knowledge_id}: "
                f"ID 不在有效候选列表中"
            )

        # 自关联检查
        if j.from_knowledge_id == j.to_knowledge_id:
            raise ValueError(
                f"候选 {j.candidate_knowledge_id}: from == to（自关联）"
            )

        # from/to ID 必须是 source 或有效候选
        allowed_ids = valid_candidate_ids | {source_id}
        if j.from_knowledge_id not in allowed_ids:
            raise ValueError(
                f"候选 {j.candidate_knowledge_id}: "
                f"from_knowledge_id={j.from_knowledge_id} 不在允许集合中"
            )
        if j.to_knowledge_id not in allowed_ids:
            raise ValueError(
                f"候选 {j.candidate_knowledge_id}: "
                f"to_knowledge_id={j.to_knowledge_id} 不在允许集合中"
            )

        # 方向标准化
        j = self._fix_direction(j, source_id)

        # 置信度范围
        if j.confidence < 0 or j.confidence > 1:
            j = j.model_copy(update={"confidence": max(0.0, min(1.0, j.confidence))})

        return j

    def _fix_direction(
        self,
        j: KnowledgeRelationJudgement,
        source_id: int,
    ) -> KnowledgeRelationJudgement:
        """根据关系语义标准化方向。

        prerequisite: from=前置知识, to=后续知识
        extension: from=基础知识, to=扩展知识
        related/contrast: 保留输入顺序（无方向语义）
        """
        if j.relation_type == "prerequisite":
            # 前置知识 → 后续知识
            # 如果 LLM 把方向搞反了（source 放在了 to 位置且 source 是后续知识）
            # 这里我们信任 LLM 的方向判断，但确保 from != to
            pass  # 方向由 LLM 语义判断，这里只做合法性检查

        elif j.relation_type == "extension":
            # 基础知识 → 扩展知识
            pass  # 方向由 LLM 语义判断

        # related/contrast: 无方向，保留原顺序
        return j
