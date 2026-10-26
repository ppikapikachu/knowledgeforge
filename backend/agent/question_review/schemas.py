"""QuestionReviewAgent 的结构化输出 Schema（执行文档 §4.3）。

枚举定义（固定，不得随意扩展）：
- decision: auto_approve / auto_reject / manual_review
- risk_level: low / medium / high / unknown
- 单项检查: pass / fail / uncertain / not_applicable
"""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

ReviewDecision = Literal["auto_approve", "auto_reject", "manual_review"]
RiskLevel = Literal["low", "medium", "high", "unknown"]
CheckResult = Literal["pass", "fail", "uncertain", "not_applicable"]

# 建议的 issue_types 枚举（§4.3）；服务端按此白名单过滤非法值
ISSUE_TYPES = (
    "incorrect_answer",
    "factual_error",
    "ambiguous_stem",
    "insufficient_context",
    "invalid_options",
    "multiple_correct_options",
    "no_correct_option",
    "knowledge_mismatch",
    "difficulty_mismatch",
    "explanation_conflict",
    "version_ambiguity",
    "outdated_content",
    "other",
)


class ReviewChecks(BaseModel):
    """8 项检查结果（§4.1）。"""

    factual_correctness: CheckResult = "not_applicable"
    answer_correctness: CheckResult = "not_applicable"
    question_clarity: CheckResult = "not_applicable"
    option_quality: CheckResult = "not_applicable"
    knowledge_alignment: CheckResult = "not_applicable"
    difficulty_alignment: CheckResult = "not_applicable"
    explanation_consistency: CheckResult = "not_applicable"
    version_environment: CheckResult = "not_applicable"


class EvidenceItem(BaseModel):
    """证据条目：必须能追溯到知识点原文摘录（§4.3）。"""

    knowledge_id: Optional[int] = Field(default=None, description="关联知识点 ID")
    source_excerpt: str = Field(default="", description="用于支持判断的知识点原文摘录")
    explanation: str = Field(default="", description="该资料如何支持当前判断")


class QuestionReviewOutput(BaseModel):
    """审核结构化输出（模型结果契约）。"""

    decision: ReviewDecision
    risk_level: RiskLevel = "unknown"
    checks: ReviewChecks = Field(default_factory=ReviewChecks)
    issue_types: List[str] = Field(default_factory=list)
    reason: str = ""
    evidence: List[EvidenceItem] = Field(default_factory=list)
