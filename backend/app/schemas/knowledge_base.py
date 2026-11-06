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
        description="展示名称，必填，长度 1-100，如 Android",
        examples=["Android"],
    )
    description: Optional[str] = Field(
        default=None,
        description="知识库简介，可选，用于说明该知识库涵盖的知识范围",
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


class KnowledgeBaseListItem(KnowledgeBaseResponse):
    """知识库列表条目（GET /knowledge-bases 的 data.items 元素）。

    字段与 KnowledgeBaseResponse 完全一致；knowledge_count 为实时聚合的知识点数量。
    """

    pass


class KnowledgeBaseMappingSelectItem(BaseModel):
    """知识库选择列表条目（题库-知识库映射配置页 GET /knowledge-bases 的 data.items 元素）。"""

    id: int = Field(description="知识库 ID")
    name: str = Field(description="展示名称")
    description: Optional[str] = Field(default=None, description="简介，可为空")
    status: str = Field(
        description="知识库状态：active=正常（status=1），disabled=停用（status=0），注意此处为字符串"
    )
    knowledge_count: int = Field(
        default=0, description="该知识库下的知识点数量"
    )


class MappedKnowledgeBaseItem(BaseModel):
    """已关联知识库条目（映射详情 data.items 元素，仅含基础信息，无 status 字段）。"""

    id: int = Field(description="知识库 ID")
    name: str = Field(description="展示名称")
    description: Optional[str] = Field(default=None, description="简介，可为空")
    knowledge_count: int = Field(
        default=0, description="该知识库下的知识点数量"
    )


class KnowledgeBaseMappingDetailResponse(BaseModel):
    """题库-知识库映射详情响应（GET /question-banks/{question_bank_id}/knowledge-bases 的 data）。"""

    question_bank_id: int = Field(description="题库 ID")
    items: List[MappedKnowledgeBaseItem] = Field(
        description="当前关联的知识库列表（基础信息数组）"
    )
    knowledge_base_ids: List[int] = Field(
        description="当前关联的知识库 ID 列表，与 items 对应"
    )


class KnowledgeBaseMappingSaveResponse(BaseModel):
    """题库-知识库映射保存响应（PUT /question-banks/{question_bank_id}/knowledge-bases 的 data）。"""

    question_bank_id: int = Field(description="题库 ID")
    knowledge_base_ids: List[int] = Field(
        description="保存后关联的知识库 ID 列表（已去重、保持传入顺序）"
    )
    updated_at: str = Field(
        description="更新时间，ISO 8601 字符串（如 2026-01-01T00:00:00），与接口现行返回一致"
    )
