"""Common schemas for API responses."""

from typing import Any, Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """Unified API response wrapper."""

    code: int = Field(default=0, description="状态码: 0=成功")
    message: str = Field(default="success", description="消息")
    data: Optional[T] = Field(default=None, description="数据")


class PaginatedData(BaseModel, Generic[T]):
    """Paginated data wrapper."""

    items: List[T] = Field(default_factory=list, description="数据列表")
    page: int = Field(description="当前页码")
    page_size: int = Field(description="每页数量")
    total: int = Field(description="总记录数")


class PaginationParams(BaseModel):
    """Pagination query parameters."""

    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页数量")


class MessageResponse(BaseModel):
    """Simple message response."""

    message: str = Field(description="消息内容")


class IdResponse(BaseModel):
    """Response with a single ID."""

    id: int = Field(description="资源ID")
