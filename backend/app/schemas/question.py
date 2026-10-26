"""Question schemas."""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class QuestionType(str, Enum):
    """Question types."""

    SINGLE_CHOICE = "SINGLE_CHOICE"
    MULTIPLE_CHOICE = "MULTIPLE_CHOICE"
    TRUE_FALSE = "TRUE_FALSE"
    SHORT_ANSWER = "SHORT_ANSWER"


class QuestionStatus(str, Enum):
    """Question status."""

    DRAFT = "pending_review"
    PUBLISHED = "published"
    DISABLED = "disabled"


class QuestionSourceType(str, Enum):
    """Question source types."""

    MANUAL = "MANUAL"
    IMPORT = "IMPORT"
    AI = "AI"


class OptionCreate(BaseModel):
    """Schema for creating a question option."""

    option_key: str = Field(
        ..., min_length=1, max_length=10, description="选项标识: A/B/C/D"
    )
    option_content: str = Field(
        ..., min_length=1, description="选项内容"
    )
    is_correct: int = Field(
        default=0, ge=0, le=1, description="是否正确: 1=正确, 0=错误"
    )
    sort_order: int = Field(default=0, ge=0, description="排序")


class OptionResponse(BaseModel):
    """Question option response schema."""

    id: int = Field(description="选项ID")
    question_id: int = Field(description="题目ID")
    option_key: str = Field(description="选项标识")
    option_content: str = Field(description="选项内容")
    is_correct: int = Field(description="是否正确")
    sort_order: int = Field(description="排序")
    created_at: datetime = Field(description="创建时间")

    class Config:
        from_attributes = True


class QuestionCreate(BaseModel):
    """Schema for creating a question."""

    question_bank_id: Optional[int] = Field(
        default=None,
        description="所属题库 ID。不传时默认使用未分类题库",
    )
    question_type: str = Field(
        ..., description="题型: SINGLE_CHOICE/MULTIPLE_CHOICE/TRUE_FALSE/SHORT_ANSWER"
    )
    content: str = Field(..., min_length=1, description="题目内容")
    answer: str = Field(..., min_length=1, description="标准答案")
    analysis: Optional[str] = Field(default=None, description="题目解析")
    difficulty: int = Field(
        default=1, ge=1, le=3, description="难度: 1=简单, 2=中等, 3=困难"
    )
    status: str = Field(
        default="pending_review", description="状态: pending_review/published/rejected/disabled"
    )
    source_type: str = Field(
        default="MANUAL", description="来源: MANUAL/IMPORT/AI"
    )
    quality_score: Optional[float] = Field(
        default=None, ge=0, le=100, description="质量评分: 0~100"
    )
    options: Optional[List[OptionCreate]] = Field(
        default=None, description="选项列表"
    )
    knowledge_ids: Optional[List[int]] = Field(
        default=None, description="关联知识点ID列表"
    )

    @model_validator(mode="after")
    def validate_question_type_and_options(self) -> "QuestionCreate":
        """Validate question type matches options."""
        qtype = self.question_type
        options = self.options or []

        if qtype == "SINGLE_CHOICE":
            if len(options) < 2:
                raise ValueError("单选题至少需要2个选项")
            correct_count = sum(1 for o in options if o.is_correct == 1)
            if correct_count != 1:
                raise ValueError("单选题必须有且仅有1个正确答案")

        elif qtype == "MULTIPLE_CHOICE":
            if len(options) < 2:
                raise ValueError("多选题至少需要2个选项")
            correct_count = sum(1 for o in options if o.is_correct == 1)
            if correct_count < 1:
                raise ValueError("多选题至少需要1个正确答案")

        elif qtype == "TRUE_FALSE":
            if options:
                raise ValueError("判断题不应有选项")
            if self.answer not in ("TRUE", "FALSE"):
                raise ValueError('判断题答案必须是 "TRUE" 或 "FALSE"')

        elif qtype == "SHORT_ANSWER":
            if options:
                raise ValueError("简答题不应有选项")

        return self


class QuestionUpdate(BaseModel):
    """Schema for updating a question."""

    question_bank_id: Optional[int] = Field(
        default=None, description="所属题库 ID"
    )
    question_type: Optional[str] = Field(default=None, description="题型")
    content: Optional[str] = Field(
        default=None, min_length=1, description="题目内容"
    )
    answer: Optional[str] = Field(
        default=None, min_length=1, description="标准答案"
    )
    analysis: Optional[str] = Field(default=None, description="题目解析")
    difficulty: Optional[int] = Field(default=None, ge=1, le=3, description="难度")
    status: Optional[str] = Field(default=None, description="状态")
    source_type: Optional[str] = Field(default=None, description="来源")
    quality_score: Optional[float] = Field(
        default=None, ge=0, le=100, description="质量评分"
    )
    options: Optional[List[OptionCreate]] = Field(
        default=None, description="选项列表(替换全部)"
    )
    knowledge_ids: Optional[List[int]] = Field(
        default=None, description="关联知识点ID列表(替换全部)"
    )


class QuestionResponse(BaseModel):
    """Question response schema."""

    id: int = Field(description="题目ID")
    question_bank_id: int = Field(description="所属题库 ID")
    question_type: str = Field(description="题型")
    content: str = Field(description="题目内容")
    answer: str = Field(description="标准答案")
    analysis: Optional[str] = Field(description="解析")
    difficulty: int = Field(description="难度")
    status: str = Field(description="状态")
    source_type: str = Field(description="来源")
    quality_score: Optional[Decimal] = Field(description="质量评分")
    used_count: int = Field(description="使用次数")
    correct_count: int = Field(description="正确次数")
    options: List[OptionResponse] = Field(
        default_factory=list, description="选项列表"
    )
    knowledge_ids: List[int] = Field(
        default_factory=list, description="关联知识点ID"
    )
    dedup_review_status: Optional[str] = Field(
        default=None,
        description="去重复核状态（uncertain/duplicate/distinct/none，详情接口返回）",
    )
    dedup_manual_resolution: Optional[str] = Field(
        default=None,
        description="人工复核结论（duplicate/distinct，未处理为 null；不覆盖自动判定）",
    )
    dedup_effective_decision: Optional[str] = Field(
        default=None,
        description="最终结论：有人工结论时优先人工结论，否则为原始自动结论",
    )
    ai_review_decision: Optional[str] = Field(
        default=None,
        description="AI 质量审核决策（auto_approve/auto_reject/manual_review，无记录为 null）",
    )
    ai_review_risk_level: Optional[str] = Field(
        default=None,
        description="AI 审核风险级别（low/medium/high/unknown）",
    )
    ai_review_reason: Optional[str] = Field(
        default=None, description="AI 审核理由"
    )
    ai_review_issue_types: Optional[List[str]] = Field(
        default=None, description="AI 审核问题类型列表"
    )
    ai_reviewed_at: Optional[str] = Field(
        default=None, description="AI 审核完成时间"
    )
    ai_review_record_id: Optional[int] = Field(
        default=None, description="AI 审核记录 ID（最新一轮）"
    )
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")

    class Config:
        from_attributes = True
