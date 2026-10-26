/**
 * AI 质量审核类型定义
 * 依据：backend/app/api/v1/question_review.py、schemas/question_review.py
 */

// ==================== 审核记录 ====================

/** 审核结论 */
export type AiReviewDecision = 'auto_approve' | 'auto_reject' | 'manual_review'

/** 风险级别 */
export type AiReviewRiskLevel = 'low' | 'medium' | 'high' | 'unknown'

/** 执行状态 */
export type AiReviewExecutionStatus = 'success' | 'failed' | 'skipped'

/** 审核检查项结果 */
export type AiCheckResult = 'pass' | 'fail' | 'uncertain' | 'not_applicable' | string

/** 审核证据 */
export interface AiReviewEvidence {
  knowledge_id: number
  source_excerpt: string
  explanation: string
}

/** 审核记录（GET /question-reviews/records） */
export interface QuestionReviewRecord {
  id: number
  question_id: number
  generation_task_id: number | null
  review_round: number
  trigger_source: string
  execution_status: AiReviewExecutionStatus
  decision: AiReviewDecision | null
  risk_level: AiReviewRiskLevel | null
  issue_types: string[]
  checks: Record<string, AiCheckResult> | null
  reason: string | null
  evidence: AiReviewEvidence[] | null
  model_name: string | null
  prompt_version: string | null
  reviewed_content_hash: string | null
  duration_ms: number | null
  error_code: string | null
  error_message: string | null
  reopened_by: number | null
  reopened_at: string | null
  reopen_reason: string | null
  question_status: string | null
  question_type: string | null
  question_bank_name: string | null
  created_at: string
}

export interface QuestionReviewRecordQueryParams {
  task_id?: number | null
  question_id?: number | null
  decision?: AiReviewDecision | null
  execution_status?: AiReviewExecutionStatus | null
  page?: number
  page_size?: number
}

// ==================== 任务审核统计 ====================

export interface TaskAiReviewStats {
  task_id: number
  enable_ai_review: boolean
  ai_review_status: string
  ai_review_total_count: number
  ai_review_processed_count: number
  ai_auto_approved_count: number
  ai_auto_rejected_count: number
  ai_manual_review_count: number
  ai_review_failed_count: number
  ai_review_skipped_count: number
  ai_review_pending_count: number
}

// ==================== reopen ====================

export interface ReopenReviewRequest {
  reason: string
}

export interface ReopenReviewResponse {
  question_id: number
  status: string
  reopened_by: number
  reopen_reason: string
  record_id: number
}
