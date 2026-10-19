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
