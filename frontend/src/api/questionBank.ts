import request from '@/utils/request'
import type { ApiResponse, PaginatedData } from '@/types/auth'
import type { QuestionBank, QuestionBankQueryParams } from '@/types/questionManagement'

export function getQuestionBankList(
  params?: QuestionBankQueryParams,
): Promise<ApiResponse<PaginatedData<QuestionBank>>> {
  return request.get('/api/v1/question-banks', { params })
}

export function getQuestionBankDetail(id: number): Promise<ApiResponse<QuestionBank>> {
  return request.get(`/api/v1/question-banks/${id}`)
}

/**
 * 设置题库是否开放普通用户练习。
 * 关闭仅阻止新组卷，不会删除历史试卷或练习会话。
 */
export function updateQuestionBankPracticeAvailability(
  id: number,
  data: { is_available_for_practice: boolean },
): Promise<ApiResponse<QuestionBank>> {
  return request.patch(`/api/v1/question-banks/${id}/practice-availability`, data)
}
