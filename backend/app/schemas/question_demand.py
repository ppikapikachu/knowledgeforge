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
    importance_level: str = Field(..., description="重要度等级：core 重要 | important 次要 | normal 一般 | supplementary 补充")


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
    knowledge_base_ids: List[int] = Field(..., description="知识库 ID 列表（全量替换语义；传空数组=清空关联；重复ID自动去重保序；任一 ID 不存在返回 40001）")


class KnowledgeBaseMappingResponse(BaseModel):
    question_bank_id: int
    knowledge_base_ids: List[int]
    updated_at: Optional[datetime] = None


class PolicyRequest(BaseModel):
    stock_weight: int = Field(default=50, ge=0, le=100, description="库存权重 0-100：当前题目库存越少的知识点得分越高（三项权重和须=100）")
    usage_weight: int = Field(default=30, ge=0, le=100, description="用量权重 0-100：近期被答题/出题使用的频率得分（三项权重和须=100）")
    importance_weight: int = Field(default=20, ge=0, le=100, description="重要度权重 0-100：知识点重要度等级得分（三项权重和须=100）")
    target_stock: int = Field(default=20, ge=1, le=500, description="目标库存题数 1-500：每个知识点期望保有的题目数量基准")
    usage_window_days: int = Field(default=30, ge=1, le=365, description="用量统计窗口天数 1-365：计算用量分数时回看的天数范围")
    recent_answers_per_question_target: int = Field(default=3, ge=1, le=100, description="每题近期答题目标次数 1-100：用量强度的饱和基准")
    usage_extra_ratio: float = Field(default=0.5, ge=0, le=2, description="用量加成比例 0-2：高频使用知识点的额外需求放大系数")
    max_per_knowledge_per_task: int = Field(default=10, ge=1, le=50, description="单任务单知识点生成上限 1-50：防止一次任务过度集中在个别知识点")
    min_demand_score: float = Field(default=0.15, ge=0, le=1, description="最低需求分 0-1：低于该需求分的知识点不参与自动分配")
    is_enabled: bool = Field(default=True, description="是否启用智能分配策略：false 时自动分配接口返回 40001")


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
    question_bank_id: int = Field(..., description="题库 ID，必须是已存在的题库（用于确定知识点范围与生效策略）")
    question_type: str = Field(default="SINGLE_CHOICE", description="目标题型：SINGLE_CHOICE|MULTIPLE_CHOICE|TRUE_FALSE|SHORT_ANSWER")
    difficulty: int = Field(default=2, ge=1, le=3, description="目标难度：1 简单 | 2 中等 | 3 困难")
    count: int = Field(..., ge=1, le=500, description="计划生成总题数 1-500（分配结果按最大余数法拆到各知识点）")


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
    allocation_mode: Optional[str] = Field(default=None, description="manual|auto：manual 按指定知识点生成，auto 按智能分配（必填其一）")
    knowledge_id: Optional[int] = Field(default=None, description="manual 模式必填：目标知识点 ID")
    question_bank_id: int = Field(..., description="题库 ID，必须是已存在的题库")
    question_type: str = Field(default="SINGLE_CHOICE", description="目标题型：SINGLE_CHOICE|MULTIPLE_CHOICE|TRUE_FALSE|SHORT_ANSWER")
    difficulty: int = Field(default=2, ge=1, le=3, description="目标难度：1 简单 | 2 中等 | 3 困难")
    count: int = Field(..., ge=1, le=500, description="计划生成总题数 1-500")
    allow_partial: bool = Field(default=False, description="是否允许部分分配：false 时库存不足直接报错不创建任务")


class TaskCreateResponse(BaseModel):
    task_id: int
    status: str
    allocation_mode: str
    requested_count: int
    allocated_count: int
    unallocated_count: int
    message: str
