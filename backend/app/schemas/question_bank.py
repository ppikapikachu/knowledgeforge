"""题库 Schema 定义。"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class QuestionBankCreate(BaseModel):
    """创建题库请求。"""

    code: str = Field(
        ..., min_length=1, max_length=50,
        description="稳定唯一标识，创建后不可修改",
        examples=["java_basic"],
    )
    name: str = Field(
        ..., min_length=1, max_length=100,
        description="显示名称（题库面向用户的可读名称，1~100 字符）",
        examples=["Java 基础"],
    )
    description: Optional[str] = Field(
        default=None,
        description="内容范围说明（描述该题库覆盖的知识范围，供管理员与选题参考；可为空）",
    )
    is_available_for_practice: Optional[bool] = Field(
        default=False,
        description="是否开放练习（普通用户可组卷练习；关闭只挡未来组卷，不删历史试卷）",
    )


class QuestionBankUpdate(BaseModel):
    """更新题库请求。"""

    name: Optional[str] = Field(default=None, max_length=100, description="显示名称（更新题库可读名称，1~100 字符；不传=不修改）")
    description: Optional[str] = Field(default=None, description="内容范围说明（更新知识范围描述；不传=不修改）")
    status: Optional[int] = Field(
        default=None, ge=0, le=1,
        description="状态筛选与更新取值：1=启用，0=停用（不传=不修改）",
    )
    is_available_for_practice: Optional[bool] = Field(
        default=None,
        description="是否开放练习（可选更新；关闭只挡未来组卷，不删历史试卷与会话）",
    )


class PracticeAvailabilityRequest(BaseModel):
    """开放练习开关请求（管理端）。"""

    is_available_for_practice: bool = Field(
        ..., description="true=开放练习（普通用户可组卷），false=关闭（只挡未来组卷，不删历史试卷与会话）"
    )


class QuestionBankResponse(BaseModel):
    """题库响应。"""

    id: int = Field(description="题库 ID（数据库主键）")
    code: str = Field(description="稳定唯一标识（创建后不可修改）")
    name: str = Field(description="显示名称（题库可读名称）")
    description: Optional[str] = Field(description="内容范围说明（知识范围描述；可为空）")
    status: int = Field(description="启用状态：1=启用，0=停用")
    is_available_for_practice: bool = Field(
        default=False, description="是否开放练习（普通用户可组卷练习）"
    )
    question_count: int = Field(default=0, description="题库下题目数量")
    published_question_count: int = Field(default=0, description="已发布（可组卷）题目数量")
    pending_review_count: int = Field(default=0, description="待审核题目数量")
    can_assemble: bool = Field(default=False, description="是否可组卷（至少 1 道已发布题）")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")

    class Config:
        from_attributes = True


class QuestionBankListItem(QuestionBankResponse):
    """题库列表条目（GET /question-banks 的 data.items 元素）。

    字段与 QuestionBankResponse 完全一致（含 published_question_count/
    pending_review_count/can_assemble 等实时聚合字段）。
    """

    pass
