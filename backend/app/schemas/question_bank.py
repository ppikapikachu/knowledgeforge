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
        description="显示名称",
        examples=["Java 基础"],
    )
    description: Optional[str] = Field(
        default=None,
        description="内容范围说明",
    )


class QuestionBankUpdate(BaseModel):
    """更新题库请求。"""

    name: Optional[str] = Field(default=None, max_length=100, description="显示名称")
    description: Optional[str] = Field(default=None, description="内容范围说明")
    status: Optional[int] = Field(
        default=None, ge=0, le=1,
        description="状态: 1=启用, 0=停用",
    )


class QuestionBankResponse(BaseModel):
    """题库响应。"""

    id: int = Field(description="题库 ID")
    code: str = Field(description="唯一标识")
    name: str = Field(description="显示名称")
    description: Optional[str] = Field(description="内容范围说明")
    status: int = Field(description="状态: 1=启用, 0=停用")
    question_count: int = Field(default=0, description="题库下题目数量")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")

    class Config:
        from_attributes = True
