"""QuestionDecisionAgent 的 Pydantic Schema。

定义出题计划的输入、输出结构。
Agent 只生成计划，不生成题目内容。
"""

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class DifficultyDistribution(BaseModel):
    """难度分配（百分比或数量）。"""

    easy: int = Field(default=33, ge=0, le=100, description="简单题占比或数量")
    medium: int = Field(default=34, ge=0, le=100, description="中等题占比或数量")
    hard: int = Field(default=33, ge=0, le=100, description="困难题占比或数量")


class QuestionDecisionRequest(BaseModel):
    """出题决策请求。"""

    question_bank_ids: List[int] = Field(
        ...,
        min_length=1,
        description="用户选择的题库 ID 列表（至少 1 个）",
        examples=[[1, 4]],
    )
    total_question_count: int = Field(
        ...,
        ge=1,
        le=200,
        description="本次计划题量",
        examples=[20],
    )
    question_types: Optional[List[str]] = Field(
        default=None,
        description="允许的题型列表，不传时不限制",
        examples=[["SINGLE_CHOICE", "SHORT_ANSWER"]],
    )
    difficulty_distribution: Optional[DifficultyDistribution] = Field(
        default=None,
        description="难度分配百分比，不传时使用默认分配",
    )


class KnowledgePlanItem(BaseModel):
    """单个知识点的出题计划。"""

    knowledge_id: int = Field(description="知识点 ID（来自候选集）")
    knowledge_name: str = Field(description="知识点名称")
    planned_count: int = Field(description="计划题量")
    question_types: List[str] = Field(description="分配的题型")
    difficulty_counts: Dict[str, int] = Field(
        description="难度分配数量: easy/medium/hard"
    )


class QuestionBankPlan(BaseModel):
    """单个题库的出题计划。"""

    question_bank_id: int = Field(description="题库 ID")
    question_bank_name: str = Field(description="题库名称")
    planned_count: int = Field(description="该题库计划题量")
    knowledge_points: List[KnowledgePlanItem] = Field(
        default_factory=list,
        description="知识点分配列表",
    )


class QuestionDecisionResponse(BaseModel):
    """出题决策响应。"""

    total_question_count: int = Field(description="用户要求的总题量")
    planned_question_count: int = Field(description="实际计划的总题量")
    question_banks: List[QuestionBankPlan] = Field(
        description="题库分配计划"
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="警告信息（如候选不足、未分配题量等）"
    )
