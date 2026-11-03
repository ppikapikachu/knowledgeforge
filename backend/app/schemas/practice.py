"""练习相关请求/响应 Schema（DTO 白名单投影，禁止 ORM 直接序列化）。"""

from decimal import Decimal
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DifficultyDistribution(BaseModel):
    easy: int = Field(default=0, ge=0, le=200)
    normal: int = Field(default=0, ge=0, le=200)
    hard: int = Field(default=0, ge=0, le=200)


class AssemblePaperRequest(BaseModel):
    question_bank_id: int = Field(
        ..., ge=1,
        description="题库 ID（必填）；必须为已开放练习（is_available_for_practice=true）的题库",
    )
    title: Optional[str] = Field(
        default=None, max_length=128,
        description="试卷标题（可选；未传时按项目约定生成默认标题）",
    )
    knowledge_ids: Optional[List[int]] = Field(
        default=None,
        description="可选：限定知识点；每个 ID 必须与指定题库存在真实关联，无效 ID 直接参数错误",
    )
    question_type_counts: Dict[str, int] = Field(
        default_factory=dict, description="题型数量 {SINGLE_CHOICE: 3, ...}"
    )
    difficulty_distribution: DifficultyDistribution = Field(
        default_factory=DifficultyDistribution,
        description="难度分布 {easy: 2, normal: 2, hard: 1}",
    )
    total_count: int = Field(..., ge=1, le=200, description="题目数量，必须与两个分布之和一致")
    allow_partial: bool = Field(
        default=False, description="库存不足时是否允许按可用量出卷（默认不允许，不静默少题）"
    )
    selection_strategy: str = Field(default="random", description="目前仅支持 random")

    @field_validator("question_type_counts")
    @classmethod
    def _check_type_counts(cls, v: Dict[str, int]) -> Dict[str, int]:
        allowed = {"SINGLE_CHOICE", "MULTIPLE_CHOICE", "TRUE_FALSE", "SHORT_ANSWER"}
        for k, n in (v or {}).items():
            if k not in allowed:
                raise ValueError(f"不支持的题型: {k}")
            if not isinstance(n, int) or n < 0:
                raise ValueError(f"题型数量必须为非负整数: {k}")
        return v

    @field_validator("selection_strategy")
    @classmethod
    def _check_strategy(cls, v: str) -> str:
        if v != "random":
            raise ValueError("selection_strategy 目前仅支持 random")
        return v


class DraftSaveRequest(BaseModel):
    answer: Any = Field(        default=None,
        description="草稿答案（按题型 JSON 值：单选/简答=字符串，多选=字符串数组，判断=布尔；仅写草稿不判分）",
    )


class MarkRequest(BaseModel):
    is_marked: bool = Field(..., description="标记状态")


class ProgressRequest(BaseModel):
    current_item_order: int = Field(..., ge=1, le=200)


class SubmitAnswerRequest(BaseModel):
    """提交答案请求：answer 按题型为不同 JSON 值（单选=字符串、多选=字符串数组、判断=布尔、简答=字符串）。

    只接受 answer/idempotency_key/time_spent_ms 三个字段，
    不接受 app_user_id/question_id/correct_answer/is_correct/score（由服务端判定或派生）。
    """
    # 严格模式：多余字段（含伪造 is_correct/score/app_user_id）一律拒绝（docs/14 补充 §9.2）
    model_config = ConfigDict(extra="forbid")

    answer: Any = Field(        ..., description="答案（按题型 JSON 值：单选=选项键字符串、多选=选项键数组、判断=布尔、简答=文本）"
    )
    idempotency_key: str = Field(..., min_length=8, max_length=64, description="幂等键")
    time_spent_ms: Optional[int] = Field(default=None, ge=0, le=86400000)

    @field_validator("idempotency_key")
    @classmethod
    def _check_key(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("idempotency_key 不能为空")
        return v
