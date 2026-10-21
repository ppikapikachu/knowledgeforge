/**
 * 题目去重类型定义
 * 依据：backend/app/api/v1/question_dedup.py、models/question_dedup_record.py、QUESTION_DEDUP_API_REFERENCE.md
 */

// ==================== 去重服务状态 ====================

export type DedupIndexStatus = 'initializing' | 'ready' | 'degraded' | 'disabled'

export interface DedupThresholds {
  same_scope_candidate_threshold: number
  cross_scope_high_threshold: number
  final_block_threshold: number
  vector_top_k: number
  keyword_top_k: number
  llm_max_candidates_per_question: number
  llm_batch_size: number
}

export interface DedupStatusData {
  enabled: boolean
  status: DedupIndexStatus
  reason: string | null
  stats: Record<string, unknown>
  failures: Array<Record<string, unknown>>
  blocking_question_count: number
  thresholds: DedupThresholds
  hash_version: string
}

// ==================== 去重审计记录 ====================

export type DedupDecision = 'duplicate' | 'distinct' | 'uncertain'

export type DedupDecisionMethod = 'exact_hash' | 'algorithm_only' | 'vector_and_llm' | 'batch_internal'

export type DedupScopeMode = 'same_scope' | 'cross_scope' | 'global_exact' | 'batch_internal'

/** 人工裁定结论（仅允许 duplicate / distinct，不接受 uncertain） */
export type ManualResolution = 'duplicate' | 'distinct'

export interface DedupRecord {
  id: number
  task_id: number | null
  new_content_hash: string
  new_hash_version: string
  new_content_snapshot: string
  new_question_type: string
  new_question_bank_id: number | null
  new_knowledge_ids: number[] | null
  matched_question_id: number | null
  matched_question_bank_id: number | null
  matched_knowledge_ids: number[] | null
  matched_source: string | null
  scope_mode: DedupScopeMode | null
  keyword_score: number
  vector_score: number
  algorithm_score: number
  llm_called: boolean
  llm_decision: DedupDecision | null
  llm_reason: string | null
  decision: DedupDecision
  decision_method: DedupDecisionMethod
  needs_manual_review: boolean
  embedding_model: string | null
  embedding_version: string | null
  created_at: string | null
  updated_at: string | null
  /** 人工裁定结论（null = 未裁定） */
  manual_resolution: ManualResolution | null
  /** 最终有效结论 = manual_resolution or decision */
  effective_decision: DedupDecision
  resolution_reason: string | null
  resolved_by: number | null
  resolved_at: string | null
}

export interface DedupRecordQueryParams {
  task_id?: number | null
  question_id?: number | null
  decision?: DedupDecision | null
  needs_manual_review?: boolean | null
  page?: number
  page_size?: number
}

// ==================== 人工复核 ====================

export interface ResolveDedupRecordRequest {
  conclusion: ManualResolution
  reason: string
}

export interface ResolveDedupRecordResponse {
  id: number
  decision: DedupDecision
  manual_resolution: ManualResolution | null
  effective_decision: DedupDecision
  needs_manual_review: boolean
  resolution_reason: string | null
  resolved_by: number | null
  resolved_at: string | null
}

// ==================== 任务去重统计 ====================

export interface TaskDedupStats {
  task_id: number | null
  records: number
  by_decision: Record<string, number>
  by_method: Record<string, number>
  llm_called: number
}

// ==================== 任务详情去重字段 ====================

export type TaskDedupReviewStatus = 'manual_review_required' | 'deduplicated' | 'clean'

// ==================== 题目去重复核状态 ====================

export type QuestionDedupReviewStatus = 'none' | 'distinct' | 'duplicate' | 'uncertain'
