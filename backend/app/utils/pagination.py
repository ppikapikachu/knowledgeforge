"""Pagination utilities."""

from typing import Any, Dict, Generic, List, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginationParams(BaseModel):
    """Pagination query parameters."""

    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页数量")

    @property
    def offset(self) -> int:
        """Calculate offset from page and page_size."""
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        """Return page_size as limit."""
        return self.page_size


class PaginatedData(BaseModel, Generic[T]):
    """Paginated response data wrapper."""

    items: List[T] = Field(default_factory=list, description="数据列表")
    page: int = Field(description="当前页码")
    page_size: int = Field(description="每页数量")
    total: int = Field(description="总记录数")

    @property
    def total_pages(self) -> int:
        """Calculate total pages."""
        if self.total == 0:
            return 0
        return (self.total + self.page_size - 1) // self.page_size
