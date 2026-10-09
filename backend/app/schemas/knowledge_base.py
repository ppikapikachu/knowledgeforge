"""知识库 Schema 定义。"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class KnowledgeBaseCreate(BaseModel):
    """创建知识库请求。"""

    code: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="稳定编码，创建后不可修改，如 android、java",
        examples=["android"],
    )
    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="展示名称",
        examples=["Android"],
    )
    description: Optional[str] = Field(
        default=None,
        description="简介",
        examples=["Android 开发相关知识"],
    )


class KnowledgeBaseUpdate(BaseModel):
    """更新知识库请求。"""

    name: Optional[str] = Field(
        default=None,
        max_length=100,
        description="展示名称",
    )
    description: Optional[str] = Field(
        default=None,
        description="简介",
    )


class KnowledgeBaseStatusUpdate(BaseModel):
    """更新知识库状态请求。"""

    status: int = Field(
        ...,
        ge=0,
        le=1,
        description="状态: 1=正常, 0=停用",
    )


class KnowledgeBaseResponse(BaseModel):
    """知识库响应。"""

    id: int = Field(description="知识库 ID")
    code: str = Field(description="稳定编码")
    name: str = Field(description="展示名称")
    description: Optional[str] = Field(description="简介")
    status: int = Field(description="状态: 1=正常, 0=停用")
    knowledge_count: int = Field(
        default=0,
        description="该知识库下的知识点数量",
    )
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")

    class Config:
        from_attributes = True
