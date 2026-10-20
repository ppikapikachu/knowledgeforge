"""知识点重要程度 + 出题策略 + 智能分配 Schemas。"""

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class ImportanceLevel(str, Enum):
    CORE = "core"
    IMPORTANT = "important"
    NORMAL = "normal"
    SUPPLEMENTARY = "supplementary"


class ImportanceSource(str, Enum):
    DEFAULT = "default"
    AGENT = "agent"
    MANUAL = "manual"


class ImportanceUpdate(BaseModel):
    importance_level: str = Field(..., description="core/important/normal/supplementary")


class ImportanceResponse(BaseModel):
    id: int
    importance_level: str
    importance_source: str
    updated_at: datetime

    class Config:
        from_attributes = True


class ImportanceLevelInfo(BaseModel):
    value: str
    label: str
    description: str
    score: float


class KnowledgeBaseMappingUpdate(BaseModel):
    knowledge_base_ids: List[int] = Field(..., description="知识库 ID 列表")


class KnowledgeBaseMappingResponse(BaseModel):
    question_bank_id: int
    knowledge_base_ids: List[int]
    updated_at: Optional[datetime] = None


class PolicyRequest(BaseModel):
    stock_weight: int = Field(default=50, ge=0, le=100)
    usage_weight: int = Field(default=30, ge=0, le=100)
    importance_weight: int = Field(default=20, ge=0, le=100)
    target_stock: int = Field(default=20, ge=1, le=500)
    usage_window_days: int = Field(default=30, ge=1, le=365)
    recent_answers_per_question_target: int = Field(default=3, ge=1, le=100)
    usage_extra_ratio: float = Field(default=0.5, ge=0, le=2)
    max_per_knowledge_per_task: int = Field(default=10, ge=1, le=50)
    min_demand_score: float = Field(default=0.15, ge=0, le=1)
    is_enabled: bool = Field(default=True)


class PolicyResponse(BaseModel):
    stock_weight: int
    usage_weight: int
    importance_weight: int
    target_stock: int
    usage_window_days: int
    recent_answers_per_question_target: int
    usage_extra_ratio: float
    max_per_knowledge_per_task: int
    min_demand_score: float
    is_enabled: bool
    version: int
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class EffectivePolicyResponse(BaseModel):
    question_bank_id: Optional[int]
    source: str  # global_default | question_bank_override
    policy: PolicyResponse
    importance_levels: List[ImportanceLevelInfo]


class AllocationPreviewRequest(BaseModel):
    question_bank_id: int
    question_type: str = Field(default="SINGLE_CHOICE")
    difficulty: int = Field(default=2, ge=1, le=3)
    count: int = Field(..., ge=1, le=500)


class AllocationItem(BaseModel):
    knowledge_id: int
    knowledge_name: str
    knowledge_base_id: int
    knowledge_base_name: str
    importance_level: str
    importance_label: str
    published_count: int
    pending_review_count: int
    reserved_count: int
    recent_used_question_count: int
    recent_answer_count: int
    stock_score: float
    usage_score: float
    importance_score: float
    demand_score: float
    demand_count: int
    allocated_count: int
    reason_codes: List[str]
    reason_summary: str


class AllocationPreviewResponse(BaseModel):
    question_bank_id: int
    allocation_mode: str
    requested_count: int
    allocatable_count: int
    unallocated_count: int
    is_fully_allocatable: bool
    policy_version: Optional[int]
    summary: dict
    allocations: List[AllocationItem]
    warnings: List[str]


class AllocationPlanItem(BaseModel):
    knowledge_id: int
    knowledge_name: str
    knowledge_base_id: int
    knowledge_base_name: str
    importance_level: str
    importance_label: str
    planned_count: int


class AllocationPlan(BaseModel):
    allocation_mode: str
    requested_count: int
    allocated_count: int
    unallocated_count: int
    policy_version: Optional[int]
    items: List[AllocationPlanItem]


class TaskCreateWithAllocation(BaseModel):
    allocation_mode: Optional[str] = Field(default=None, description="manual|auto")
    knowledge_id: Optional[int] = Field(default=None, description="manual 模式必填")
    question_bank_id: int
    question_type: str = Field(default="SINGLE_CHOICE")
    difficulty: int = Field(default=2, ge=1, le=3)
    count: int = Field(..., ge=1, le=500)
    allow_partial: bool = Field(default=False)


class TaskCreateResponse(BaseModel):
    task_id: int
    status: str
    allocation_mode: str
    requested_count: int
    allocated_count: int
    unallocated_count: int
    message: str
