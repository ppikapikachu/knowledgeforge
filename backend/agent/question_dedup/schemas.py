"""题目查重 LLM 复核的 Pydantic Schema（结构化输出）。"""

from typing import List, Literal

from pydantic import BaseModel, Field

# 复核结论三态：重复 / 不重复 / 不确定（不确定=保留新题并标记人工复核）
VerdictLiteral = Literal["duplicate", "distinct", "uncertain"]


class LLMReviewItem(BaseModel):
    """单组配对的复核结论。"""

    pair_id: int = Field(description="配对编号，与输入的 pair_id 一致")
    verdict: VerdictLiteral = Field(description="duplicate=实质重复, distinct=不重复, uncertain=无法确定")
    reason: str = Field(default="", description="一句话判定理由")


class LLMReviewOutput(BaseModel):
    """一次 LLM 复核调用的批量输出。"""

    pairs: List[LLMReviewItem] = Field(default_factory=list, description="每组配对一条结论")
