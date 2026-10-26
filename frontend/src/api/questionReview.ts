import request from '@/utils/request'
import type { ApiResponse, PaginatedData } from '@/types/auth'
import type {
  QuestionReviewRecord,
  QuestionReviewRecordQueryParams,
  TaskAiReviewStats,
  ReopenReviewRequest,
  ReopenReviewResponse,
} from '@/types/questionReview'
import type {
  ReviewBatchRequest,
  ReviewBatchPreviewResponse,
  ReviewBatchCreateResponse,
  ReviewBatchSummary,
  ReviewBatchDetail,
  ReviewBatchQueryParams,
} from '@/types/questionReviewBatch'

/**
 * 查询 AI 审核记录
 * GET /api/v1/question-reviews/records
 */
export function getReviewRecords(
  params: QuestionReviewRecordQueryParams,
): Promise<ApiResponse<PaginatedData<QuestionReviewRecord>>> {
  return request.get('/api/v1/question-reviews/records', { params })
}

/**
 * 获取任务 AI 审核统计
 * GET /api/v1/question-reviews/stats/{task_id}
 */
export function getTaskReviewStats(taskId: number): Promise<ApiResponse<TaskAiReviewStats>> {
  return request.get(`/api/v1/question-reviews/stats/${taskId}`)
}

/**
 * AI 驳回题目重新开启人工审核
 * POST /api/v1/question-reviews/questions/{question_id}/reopen
 */
export function reopenQuestionReview(
  questionId: number,
  payload: ReopenReviewRequest,
): Promise<ApiResponse<ReopenReviewResponse>> {
  return request.post(`/api/v1/question-reviews/questions/${questionId}/reopen`, payload)
}

/**
 * 批量 AI 审核预检
 * POST /api/v1/question-reviews/batches/preview
 */
export function previewQuestionReviewBatch(
  payload: ReviewBatchRequest,
): Promise<ApiResponse<ReviewBatchPreviewResponse>> {
  return request.post('/api/v1/question-reviews/batches/preview', payload)
}

/**
 * 创建批量 AI 审核批次
 * POST /api/v1/question-reviews/batches
 */
export function createQuestionReviewBatch(
  payload: ReviewBatchRequest,
): Promise<ApiResponse<ReviewBatchCreateResponse>> {
  return request.post('/api/v1/question-reviews/batches', payload)
}

/**
 * 批量审核批次列表
 * GET /api/v1/question-reviews/batches?status=&created_by=&page=&page_size=
 */
export function getQuestionReviewBatches(
  params: ReviewBatchQueryParams,
): Promise<ApiResponse<PaginatedData<ReviewBatchSummary>>> {
  return request.get('/api/v1/question-reviews/batches', { params })
}

/**
 * 批量审核批次详情
 * GET /api/v1/question-reviews/batches/{batch_id}
 */
export function getQuestionReviewBatchDetail(
  batchId: number,
): Promise<ApiResponse<ReviewBatchDetail>> {
  return request.get(`/api/v1/question-reviews/batches/${batchId}`)
}
