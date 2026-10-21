/**
 * 题库管理模块类型定义
 *
 * 字段依据：backend/app/api/v1/question_bank.py、question_generation.py、question.py
 * 与 backend/app/models/question.py、question_generation_task.py 的真实返回。
 */

// ==================== 题库 ====================

export interface QuestionBank {
  id: number
  code: string
  name: string
  description: string | null
  status: number // 1=启用 0=停用
  question_count: number
  created_at: string
  updated_at: string
}

export interface QuestionBankQueryParams {
  page?: number
  page_size?: number
  keyword?: string | null
  status?: number | null
}

// ==================== 生成任务 ====================

/** 任务状态（模型真实取值） */
export type TaskStatus =
  | 'pending'
  | 'running'
  | 'success'
  | 'partial_success'
  | 'failed'
  | 'cancelled'

/** 创建任务请求体 */
export interface GenerationTaskCreateRequest {
  knowledge_id: number
  question_bank_id: number
  question_type: string
  difficulty: number
  count: number
}

/** 创建任务响应 data */
export interface GenerationTaskCreateResponse {
  task_id: number
  status: string
  message: string
}

/** 任务列表项（GET /question-generation/tasks） */
export interface GenerationTask {
  id: number
  status: TaskStatus
  allocation_mode: string | null
  requested_count: number | null
  allocated_count: number | null
  unallocated_count: number | null
  total_count: number
  success_count: number
  duplicate_count: number
  generated_count: number
  exact_duplicate_count: number
  semantic_duplicate_count: number
  uncertain_count: number
  unfulfilled_count: number
  failed_count: number
  request_config: Record<string, unknown> | null
  error_summary: string | null
  started_at: string | null
  completed_at: string | null
  created_at: string | null
}

/** 任务详情中关联的题目摘要（后端截断 content 至 100 字） */
export interface GenerationTaskQuestionSummary {
  id: number
  question_type: string
  content: string
  difficulty: number
  status: string
  knowledge_ids: number[]
  option_count: number
}

/** 任务详情（GET /question-generation/tasks/{id}） */
export interface GenerationTaskDetail {
  task_id: number
  created_by: number
  status: TaskStatus
  allocation_mode: string | null
  allocation_plan: {
    allocation_mode: string
    requested_count: number
    allocated_count: number
    unallocated_count: number
    policy_version: number | null
    items: Array<{
      knowledge_id: number
      knowledge_name: string
      knowledge_base_id: number
      knowledge_base_name: string
      importance_level: string
      importance_label: string
      planned_count: number
    }>
  } | null
  requested_count: number | null
  allocated_count: number | null
  unallocated_count: number | null
  request_config: Record<string, unknown> | null
  total_count: number
  success_count: number
  duplicate_count: number
  generated_count: number
  exact_duplicate_count: number
  semantic_duplicate_count: number
  uncertain_count: number
  unfulfilled_count: number
  failed_count: number
  dedup_review_status: 'manual_review_required' | 'deduplicated' | 'clean'
  dedup_manual_review_count: number
  progress: number
  error_summary: string | null
  started_at: string | null
  completed_at: string | null
  created_at: string | null
  questions: GenerationTaskQuestionSummary[]
}

export interface GenerationTaskQueryParams {
  page?: number
  page_size?: number
  status?: string | null
}

// ==================== 题目审核 ====================

export interface QuestionReviewRequest {
  action: 'publish' | 'reject'
  reason?: string
}

export interface QuestionReviewResponse {
  question_id: number
  status: string
  reviewed_by: number
  reviewed_at: string
}
