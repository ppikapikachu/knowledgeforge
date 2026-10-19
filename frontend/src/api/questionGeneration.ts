import request from '@/utils/request'
import type { ApiResponse, PaginatedData } from '@/types/auth'
import type {
  GenerationTask,
  GenerationTaskCreateRequest,
  GenerationTaskCreateResponse,
  GenerationTaskDetail,
  GenerationTaskQueryParams,
  QuestionReviewRequest,
  QuestionReviewResponse,
} from '@/types/questionManagement'

/**
 * 创建题目生成任务
 * POST /api/v1/question-generation/tasks
 * data: { task_id, status, message }
 */
export function createGenerationTask(
  data: GenerationTaskCreateRequest,
): Promise<ApiResponse<GenerationTaskCreateResponse>> {
  return request.post('/api/v1/question-generation/tasks', data)
}

/**
 * 生成任务列表
 * GET /api/v1/question-generation/tasks?page=&page_size=&status=
 */
export function getGenerationTaskList(
  params: GenerationTaskQueryParams,
): Promise<ApiResponse<PaginatedData<GenerationTask>>> {
  return request.get('/api/v1/question-generation/tasks', { params })
}

/**
 * 生成任务详情（含关联题目摘要）
 * GET /api/v1/question-generation/tasks/{id}
 */
export function getGenerationTaskDetail(id: number): Promise<ApiResponse<GenerationTaskDetail>> {
  return request.get(`/api/v1/question-generation/tasks/${id}`)
}

/**
 * 审核题目（发布/驳回）
 * POST /api/v1/question-generation/questions/{id}/review
 * body: { action: 'publish'|'reject', reason }
 */
export function reviewQuestion(
  questionId: number,
  data: QuestionReviewRequest,
): Promise<ApiResponse<QuestionReviewResponse>> {
  return request.post(`/api/v1/question-generation/questions/${questionId}/review`, data)
}
