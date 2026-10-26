import request from '@/utils/request'
import type { ApiResponse, PaginatedData } from '@/types/auth'
import type {
  QuestionReviewRecord,
  QuestionReviewRecordQueryParams,
  TaskAiReviewStats,
  ReopenReviewRequest,
  ReopenReviewResponse,
} from '@/types/questionReview'

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
