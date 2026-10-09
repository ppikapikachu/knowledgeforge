"""Knowledge schemas."""

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class KnowledgeDifficulty(int, Enum):
    """Knowledge difficulty levels."""

    EASY = 1
    MEDIUM = 2
    HARD = 3


class KnowledgeStatus(int, Enum):
    """Knowledge status."""

    ACTIVE = 1
    DISABLED = 0


class KnowledgeSourceType(str, Enum):
    """Knowledge source types."""

    MANUAL = "MANUAL"
    IMPORT = "IMPORT"
    AI = "AI"


class RelationType(str, Enum):
    """Knowledge relation types."""

    PREREQUISITE = "prerequisite"
    RELATED = "related"
    EXTENSION = "extension"
    CONTRAST = "contrast"


class KnowledgeCreate(BaseModel):
    """Schema for creating a knowledge point."""

    knowledge_base_id: Optional[int] = Field(
        default=None,
        description="所属知识库 ID。不传时默认使用未分类(uncategorized)",
    )
    name: str = Field(
        ..., min_length=1, max_length=200, description="知识点名称"
    )
    summary: Optional[str] = Field(
        default=None, max_length=1000, description="简要说明"
    )
    content: Optional[str] = Field(
        default=None, description="完整知识内容"
    )
    difficulty: int = Field(
        default=1, ge=1, le=3, description="难度: 1=简单, 2=中等, 3=困难"
    )
    status: int = Field(default=1, ge=0, le=1, description="状态: 1=正常, 0=禁用")
    source_type: str = Field(
        default="MANUAL",
        description="来源: MANUAL/IMPORT/AI",
    )
    source_document: Optional[str] = Field(
        default=None, max_length=500, description="来源文档"
    )
    keywords: Optional[List[str]] = Field(
        default=None, description="关键词列表"
    )


class KnowledgeUpdate(BaseModel):
    """Schema for updating a knowledge point."""

    knowledge_base_id: Optional[int] = Field(
        default=None, description="所属知识库 ID"
    )
    name: Optional[str] = Field(
        default=None, min_length=1, max_length=200, description="知识点名称"
    )
    summary: Optional[str] = Field(
        default=None, max_length=1000, description="简要说明"
    )
    content: Optional[str] = Field(
        default=None, description="完整知识内容"
    )
    difficulty: Optional[int] = Field(
        default=None, ge=1, le=3, description="难度"
    )
    status: Optional[int] = Field(default=None, ge=0, le=1, description="状态")
    source_type: Optional[str] = Field(default=None, description="来源")
    source_document: Optional[str] = Field(
        default=None, max_length=500, description="来源文档"
    )
    keywords: Optional[List[str]] = Field(
        default=None, description="关键词列表"
    )


class KnowledgeResponse(BaseModel):
    """Knowledge point response schema."""

    id: int = Field(description="知识点ID")
    knowledge_base_id: int = Field(description="所属知识库 ID")
    name: str = Field(description="知识点名称")
    summary: Optional[str] = Field(description="简要说明")
    content: Optional[str] = Field(description="完整内容")
    difficulty: int = Field(description="难度")
    status: int = Field(description="状态")
    source_type: str = Field(description="来源")
    source_document: Optional[str] = Field(description="来源文档")
    keywords: Optional[list] = Field(description="关键词")
    question_count: int = Field(default=0, description="关联题目数量")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")

    class Config:
        from_attributes = True


class KnowledgeRelationCreate(BaseModel):
    """Schema for creating a knowledge relation."""

    target_knowledge_id: int = Field(..., description="目标知识点ID")
    relation_type: str = Field(
        ...,
        description="关系类型: prerequisite/related/extension/contrast",
    )


class KnowledgeRelationResponse(BaseModel):
    """Knowledge relation response schema."""

    id: int = Field(description="关系ID")
    source_knowledge_id: int = Field(description="源知识点ID")
    target_knowledge_id: int = Field(description="目标知识点ID")
    relation_type: str = Field(description="关系类型")
    target_knowledge_name: Optional[str] = Field(
        default=None, description="目标知识点名称"
    )
    created_at: datetime = Field(description="创建时间")

    class Config:
        from_attributes = True
