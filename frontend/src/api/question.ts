import request from '@/utils/request'
import type { ApiResponse, PaginatedData } from '@/types/auth'
import type {
  Question,
  QuestionCreateRequest,
  QuestionUpdateRequest,
  QuestionQueryParams,
} from '@/types/question'

export function getQuestionList(params: QuestionQueryParams): Promise<ApiResponse<PaginatedData<Question>>> {
  return request.get('/api/v1/questions', { params })
}

export function getQuestionDetail(id: number): Promise<ApiResponse<Question>> {
  return request.get(`/api/v1/questions/${id}`)
}

export function createQuestion(data: QuestionCreateRequest): Promise<ApiResponse<Question>> {
  return request.post('/api/v1/questions', data)
}

export function updateQuestion(id: number, data: QuestionUpdateRequest): Promise<ApiResponse<Question>> {
  return request.put(`/api/v1/questions/${id}`, data)
}

export function deleteQuestion(id: number): Promise<ApiResponse<null>> {
  return request.delete(`/api/v1/questions/${id}`)
}
