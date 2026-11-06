"""答题记录相关响应 Schema。"""

from typing import Optional

from pydantic import BaseModel, Field


# ==================== 响应模型 ====================


class AnswerSubmitResponse(BaseModel):
    """data 载荷：提交答题后的判分结果（POST /answers/submit）。

    新建记录时不含 idempotent（或为 null）；命中幂等（相同 idempotency_key 重复提交）
    返回原记录且 idempotent=true。
    """

    record_id: int = Field(description="答题记录 ID（question_answer_record 表主键）")
    is_correct: Optional[int] = Field(default=None, description="判分结果（1=正确 0=错误 null=未判分，简答题为 null）")
    grading_status: str = Field(description="判分状态（graded=已判分 / ungraded=未判分）")
    idempotent: Optional[bool] = Field(default=None, description="是否命中幂等（命中已有记录时为 true，新建记录为 null）")


class AnswerRecordResponse(BaseModel):
    """data 载荷：单条答题记录详情（GET /answers/{record_id}）。"""

    id: int = Field(description="答题记录 ID")
    question_id: int = Field(description="题目 ID")
    user_answer: Optional[str] = Field(default=None, description="用户作答内容（可空）")
    is_correct: Optional[int] = Field(default=None, description="是否正确（1=正确 0=错误 null=未判分）")
    grading_status: str = Field(description="判分状态（graded=已判分 / ungraded=未判分）")
    score: Optional[float] = Field(default=None, description="得分（可空）")
    time_spent_ms: Optional[int] = Field(default=None, description="作答耗时毫秒（可空）")
    practice_paper_id: Optional[int] = Field(default=None, description="所属练习卷 ID（自由刷题为空）")
    practice_paper_item_id: Optional[int] = Field(default=None, description="所属练习卷题目 ID（自由刷题为空）")
    practice_session_id: Optional[int] = Field(default=None, description="所属练习会话 ID（自由刷题为空）")
    idempotency_key: Optional[str] = Field(default=None, description="幂等键（可空）")
    created_at: Optional[str] = Field(default=None, description="提交时间（ISO 8601 字符串，可空）")


class AnswerRecordItem(AnswerRecordResponse):
    """items 数组元素：答题记录条目（字段同 AnswerRecordResponse）。"""


class AnswerStatisticsResponse(BaseModel):
    """data 载荷：题目答题统计（GET /answers/statistics/{question_id}，兼容旧字段名 + 统一口径新字段）。"""

    graded_attempt_count: int = Field(description="已判分提交次数")
    correct_attempt_count: int = Field(description="判分正确次数")
    attempt_accuracy: Optional[float] = Field(default=None, description="全部提交正确率（可空，样本不足为 null）")
    first_attempt_user_count: int = Field(description="首次作答统计的用户数（分母）")
    first_attempt_correct_count: int = Field(description="首次作答正确数")
    first_attempt_accuracy: Optional[float] = Field(default=None, description="首次作答正确率（可空）")
    unique_user_count: int = Field(description="独立作答用户数")
    is_sample_sufficient: bool = Field(description="样本是否充足（true/false）")
    accuracy: Optional[float] = Field(default=None, description="同 attempt_accuracy（统一口径字段，可空）")
    display_status: str = Field(description="统计状态（available=样本充足 / insufficient_samples=样本不足）")
    sample_threshold: int = Field(description="样本量阈值（QUESTION_STATISTICS_MIN_SAMPLES，默认 20）")
