"""Import task schemas."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ImportTaskStatus(str, Enum):
    """Import task status."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ImportTaskResponse(BaseModel):
    """Import task response schema."""

    id: int = Field(description="任务ID")
    file_name: str = Field(description="原始文件名")
    file_path: str = Field(description="保存路径")
    file_size: int = Field(description="文件大小(字节)")
    file_type: str = Field(description="文件类型")
    status: str = Field(description="任务状态")
    progress: int = Field(description="进度: 0~100")
    current_step: Optional[str] = Field(description="当前阶段")
    error_message: Optional[str] = Field(description="错误信息")
    created_by: int = Field(description="创建管理员ID")
    started_at: Optional[datetime] = Field(description="开始时间")
    finished_at: Optional[datetime] = Field(description="完成时间")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")

    class Config:
        from_attributes = True
