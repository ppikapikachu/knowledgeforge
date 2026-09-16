"""知识点提取结果校验器模块。

本模块对 LLM 返回的知识点候选进行字段完整性和合法性校验。
虽然 Pydantic Schema 已经做了基础校验，但 Validator 提供更细致的业务规则校验。

校验规则：
    - name: 非空，长度 <= 200
    - summary: 非空
    - content: 非空
    - difficulty: 必须为 1/2/3
    - keywords: 非空，1~15 个，不含空值
    - source_chunk_id: 非空

校验不通过的候选会被过滤掉，不会出现在最终结果中。
错误信息会被记录到 errors 列表，不影响其他 Chunk 的处理。
"""

import logging
from typing import List, Tuple

from agent.knowledge_extract.schemas import KnowledgeCandidate

logger = logging.getLogger(__name__)


class KnowledgeValidator:
    """知识点候选校验器。

    使用方法：
        validator = KnowledgeValidator()
        valid, errors = validator.validate_candidates(candidates, "chunk_001")
    """

    def validate_candidates(
        self,
        candidates: List[KnowledgeCandidate],
        chunk_id: str,
    ) -> Tuple[List[KnowledgeCandidate], List[str]]:
        """校验知识点候选列表。

        逐个校验候选，通过校验的加入 valid 列表，
        未通过的记录错误信息到 errors 列表。

        Args:
            candidates: 待校验的知识点候选列表
            chunk_id: 来源 Chunk ID，用于错误日志定位

        Returns:
            (有效候选列表, 错误信息列表)
        """
        valid = []
        errors = []

        for i, candidate in enumerate(candidates):
            try:
                self._validate_single(candidate)
                valid.append(candidate)
            except ValueError as e:
                error_msg = (
                    f"Chunk {chunk_id}, 知识点 #{i+1} '{candidate.name}': {e}"
                )
                errors.append(error_msg)
                logger.warning(error_msg)

        return valid, errors

    def _validate_single(self, candidate: KnowledgeCandidate) -> None:
        """校验单个知识点候选。

        Args:
            candidate: 待校验的知识点候选

        Raises:
            ValueError: 校验失败时抛出，包含具体的失败原因
        """
        # ---- 名称校验 ----
        if not candidate.name or not candidate.name.strip():
            raise ValueError("name 不能为空")
        if len(candidate.name) > 200:
            raise ValueError(f"name 过长: {len(candidate.name)} > 200")

        # ---- 概述校验 ----
        if not candidate.summary or not candidate.summary.strip():
            raise ValueError("summary 不能为空")

        # ---- 内容校验 ----
        if not candidate.content or not candidate.content.strip():
            raise ValueError("content 不能为空")

        # ---- 难度校验 ----
        if candidate.difficulty not in (1, 2, 3):
            raise ValueError(
                f"difficulty 必须为 1/2/3, 实际为: {candidate.difficulty}"
            )

        # ---- 关键词校验 ----
        if not candidate.keywords:
            raise ValueError("keywords 不能为空")
        if len(candidate.keywords) < 1:
            raise ValueError("keywords 至少需要 1 个")
        if len(candidate.keywords) > 15:
            raise ValueError(f"keywords 过多: {len(candidate.keywords)} > 15")

        # 检查是否有空关键词
        for kw in candidate.keywords:
            if not kw or not kw.strip():
                raise ValueError("keywords 中存在空值")

        # ---- 来源校验 ----
        if not candidate.source_chunk_id:
            raise ValueError("source_chunk_id 不能为空")
