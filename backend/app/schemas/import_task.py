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
    file_path: str = Field(description="保存路径（相对路径 uploads/YYYY/MM/DD/文件名）")
    file_size: int = Field(description="文件大小(字节)")
    file_type: str = Field(description="文件类型：pdf/docx/txt/md")
    status: str = Field(description="任务状态：PENDING/RUNNING/SUCCESS/PARTIAL_SUCCESS/FAILED/CANCELLED")
    progress: int = Field(description="进度: 0~100")
    current_step: Optional[str] = Field(description="当前阶段（解析/抽取/去重/关联等）")
    error_message: Optional[str] = Field(description="错误信息（无错误时为 null）")
    created_by: int = Field(description="创建管理员ID")
    knowledge_base_id: int = Field(description="目标知识库 ID")
    started_at: Optional[datetime] = Field(description="开始时间")
    finished_at: Optional[datetime] = Field(description="完成时间")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")

    class Config:
        from_attributes = True


class ImportTaskCreateResponse(BaseModel):
    """创建导入任务响应（POST /import-tasks 的 data）。"""

    task_id: int = Field(description="中文：新建导入任务 ID（可通过 GET /import-tasks/{id} 查询进度）")


class ImportTaskActionResponse(BaseModel):
    """导入任务受理响应（POST /import-tasks/{task_id}/run 与 /relations/retry 的 data）。"""

    task_id: int = Field(description="中文：导入任务 ID")
    status: str = Field(description="中文：受理状态（恒为 ACCEPTED=已提交后台执行）")
    message: str = Field(description="中文：受理提示文案")
