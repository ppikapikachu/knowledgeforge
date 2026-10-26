/**
 * AI 批量审核类型定义
 * 依据：backend/app/api/v1/question_review.py + question_review_batch_service.py
 */

// ==================== 枚举 ====================

export type ReviewBatchStatus = 'queued' | 'running' | 'completed' | 'partial' | 'failed' | 'cancelled'

export type ReviewBatchItemStatus = 'queued' | 'running' | 'completed' | 'failed' | 'skipped'

export type ReviewDecision = 'auto_approve' | 'auto_reject' | 'manual_review'

export type ReviewTriggerSource = 'generation_task' | 'manual_batch'

export type ReviewRiskLevel = 'low' | 'medium' | 'high' | 'unknown'

export type ReviewExecutionStatus = 'success' | 'failed' | 'skipped'

// ==================== 预检 ====================

export interface ReviewBatchRequest {
  question_ids: number[]
}

export interface ReviewBatchPreviewItem {
  question_id: number
  eligible: boolean
  reason_code: string
  reason: string
}

export interface ReviewBatchPreviewResponse {
  requested: number
  eligible: number
  ineligible: number
  eligible_question_ids: number[]
  items: ReviewBatchPreviewItem[]
}

// ==================== 创建批次 ====================

export interface ReviewBatchCreateResponse {
  batch_id: number
  status: ReviewBatchStatus
  requested: number
  accepted: number
  skipped: number
}

// ==================== 批次摘要（列表项） ====================

export interface ReviewBatchSummary {
  id: number
  created_by: number
  status: ReviewBatchStatus
  total_count: number
  accepted_count: number
  processed_count: number
  auto_approved_count: number
  auto_rejected_count: number
  manual_review_count: number
  failed_count: number
  skipped_count: number
  pending_count: number
  started_at: string | null
  finished_at: string | null
  error_message: string | null
  created_at: string | null
  updated_at: string | null
}

export interface ReviewBatchQueryParams {
  status?: ReviewBatchStatus | null
  created_by?: number | null
  page?: number
  page_size?: number
}

// ==================== 批次详情 ====================

export interface ReviewBatchEvidenceSummary {
  knowledge_id: number | null
  explanation: string
}

export interface ReviewBatchItem {
  id: number
  question_id: number
  question_content: string | null
  question_type: string | null
  question_status: string | null
  status: ReviewBatchItemStatus
  skip_reason: string | null
  skip_reason_text: string | null
  error_code: string | null
  error_message: string | null
  review_record_id: number | null
  review_decision: ReviewDecision | null
  review_risk_level: ReviewRiskLevel | null
  review_reason: string | null
  review_issue_types: string[]
  review_evidence_summary: ReviewBatchEvidenceSummary[]
  started_at: string | null
  finished_at: string | null
}

export interface ReviewBatchProgress {
  processed: number
  accepted: number
  pending: number
}

export interface ReviewBatchDetail extends ReviewBatchSummary {
  progress: ReviewBatchProgress
  items: ReviewBatchItem[]
}

// ==================== 审核记录（扩展 batch_id / trigger_source） ====================

export interface ReviewRecord {
  id: number
  question_id: number
  generation_task_id: number | null
  batch_id: number | null
  review_round: number
  trigger_source: ReviewTriggerSource
  execution_status: ReviewExecutionStatus
  decision: ReviewDecision | null
  risk_level: ReviewRiskLevel | null
  issue_types: string[]
  checks: Record<string, string> | null
  reason: string | null
  evidence: Array<Record<string, unknown>> | null
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
  created_at: string | null
}

export interface ReviewRecordQueryParams {
  task_id?: number | null
  question_id?: number | null
  decision?: ReviewDecision | null
  execution_status?: ReviewExecutionStatus | null
  batch_id?: number | null
  trigger_source?: ReviewTriggerSource | null
  page?: number
  page_size?: number
}
