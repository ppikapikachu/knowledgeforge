/**
 * 题库智能出题 & 策略管理类型定义
 *
 * 字段依据：backend/app/schemas/question_demand.py、question_generation.py、knowledge.py
 * 与后端实际 Pydantic Schema 逐字段对齐（非文档示例）。
 */

// ==================== 枚举 ====================

/** 知识点重要程度 */
export type ImportanceLevel = 'core' | 'important' | 'normal' | 'supplementary'

/** 重要程度来源 */
export type ImportanceSource = 'default' | 'agent' | 'manual'

/** 分配模式 */
export type AllocationMode = 'manual' | 'auto'

/** 策略来源（后端实际值） */
export type PolicySource = 'global_default' | 'question_bank_override'

// ==================== 知识点重要程度 ====================

export interface KnowledgeImportanceUpdateRequest {
  importance_level: ImportanceLevel
}

/** 后端 ImportanceResponse：字段名是 id，不是 knowledge_id */
export interface KnowledgeImportanceResponse {
  id: number
  importance_level: ImportanceLevel
  importance_source: ImportanceSource
  updated_at: string
}

// ==================== 题库-知识库映射 ====================

export interface KnowledgeBaseMappingItem {
  id: number
  name: string
  description: string | null
  knowledge_count: number
}

export interface QuestionBankKnowledgeBasesData {
  question_bank_id: number
  items: KnowledgeBaseMappingItem[]
  knowledge_base_ids: number[]
}

export interface QuestionBankKnowledgeBasesUpdateRequest {
  knowledge_base_ids: number[]
}

export interface QuestionBankKnowledgeBasesUpdateData {
  question_bank_id: number
  knowledge_base_ids: number[]
  updated_at: string
}

// ==================== 出题策略 ====================

/** 后端 PolicyRequest/PolicyResponse */
export interface GenerationPolicy {
  stock_weight: number
  usage_weight: number
  importance_weight: number
  target_stock: number
  usage_window_days: number
  recent_answers_per_question_target: number
  usage_extra_ratio: number
  max_per_knowledge_per_task: number
  min_demand_score: number
  is_enabled: boolean
  version?: number
  updated_at?: string
}

/** 策略字段约束（与后端 PolicyRequest 对齐） */
export interface PolicyConstraints {
  stock_weight: { min: number; max: number }
  usage_weight: { min: number; max: number }
  importance_weight: { min: number; max: number }
  target_stock: { min: number; max: number }
  usage_window_days: { min: number; max: number }
  recent_answers_per_question_target: { min: number; max: number }
  usage_extra_ratio: { min: number; max: number }
  max_per_knowledge_per_task: { min: number; max: number }
  min_demand_score: { min: number; max: number }
}

export interface EffectivePolicyResponse {
  question_bank_id: number | null
  source: PolicySource
  policy: GenerationPolicy
  importance_levels: ImportanceLevelInfo[]
}

export interface ImportanceLevelInfo {
  value: ImportanceLevel
  label: string
  description: string
  score: number
}

// ==================== 智能分配预览 ====================

/** 预览请求（实际后端 AllocationPreviewRequest） */
export interface AllocationPreviewRequest {
  question_bank_id: number
  question_type: string
  difficulty: number
  count: number
}

/** 预览单项（后端 AllocationItem，17 字段） */
export interface AllocationPreviewItem {
  knowledge_id: number
  knowledge_name: string
  knowledge_base_id: number
  knowledge_base_name: string
  importance_level: ImportanceLevel
  importance_label: string
  published_count: number
  pending_review_count: number
  reserved_count: number
  recent_used_question_count: number
  recent_answer_count: number
  stock_score: number
  usage_score: number
  importance_score: number
  demand_score: number
  demand_count: number
  allocated_count: number
  reason_codes: string[]
  reason_summary: string
}

/** 预览响应（后端 AllocationPreviewResponse） */
export interface AllocationPreviewData {
  question_bank_id: number
  allocation_mode: string
  requested_count: number
  allocatable_count: number
  unallocated_count: number
  is_fully_allocatable: boolean
  policy_version: number | null
  summary: Record<string, unknown>
  allocations: AllocationPreviewItem[]
  warnings: string[]
}

// ==================== 任务创建 ====================

/** 后端 TaskCreateWithAllocation */
export interface TaskCreateRequest {
  allocation_mode?: AllocationMode | null
  knowledge_id?: number | null
  question_bank_id: number
  question_type: string
  difficulty: number
  count: number
  allow_partial?: boolean
  enable_ai_review?: boolean
}

/** 后端 TaskCreateResponse */
export interface TaskCreateResponseData {
  task_id: number
  status: string
  allocation_mode: AllocationMode
  requested_count: number
  allocated_count: number
  unallocated_count: number
  message: string
}

// ==================== 分配计划（任务详情） ====================

/** 后端 AllocationPlanItem */
export interface AllocationPlanItem {
  knowledge_id: number
  knowledge_name: string
  knowledge_base_id: number
  knowledge_base_name: string
  importance_level: ImportanceLevel
  importance_label: string
  planned_count: number
}

/** 后端 allocation_plan 是对象，不是数组 */
export interface AllocationPlan {
  allocation_mode: AllocationMode
  requested_count: number
  allocated_count: number
  unallocated_count: number
  policy_version: number | null
  items: AllocationPlanItem[]
}

/** 任务列表项（含分配信息） */
export interface GenerationTaskListItem {
  id: number
  status: string
  allocation_mode: string | null
  requested_count: number | null
  allocated_count: number | null
  unallocated_count: number | null
  total_count: number
  success_count: number
  duplicate_count: number
  failed_count: number
  request_config: Record<string, unknown> | null
  error_summary: string | null
  started_at: string | null
  completed_at: string | null
  created_at: string | null
}

/** 任务详情（含分配计划） */
export interface GenerationTaskDetailData {
  task_id: number
  created_by: number
  status: string
  allocation_mode: string | null
  allocation_plan: AllocationPlan | null
  requested_count: number | null
  allocated_count: number | null
  unallocated_count: number | null
  request_config: Record<string, unknown> | null
  total_count: number
  success_count: number
  duplicate_count: number
  failed_count: number
  progress: number
  error_summary: string | null
  started_at: string | null
  completed_at: string | null
  created_at: string | null
  questions: Array<{
    id: number
    question_type: string
    content: string
    difficulty: number
    status: string
    knowledge_ids: number[]
    option_count: number
  }>
}
