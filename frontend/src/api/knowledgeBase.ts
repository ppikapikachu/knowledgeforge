import request from '@/utils/request'
import type { ApiResponse, PaginatedData } from '@/types/auth'
import type {
  KnowledgeBase,
  KnowledgeBaseCreateRequest,
  KnowledgeBaseUpdateRequest,
  KnowledgeBaseStatusRequest,
  KnowledgeBaseQueryParams,
} from '@/types/knowledgeBase'

export function getKnowledgeBaseList(
  params?: KnowledgeBaseQueryParams,
): Promise<ApiResponse<PaginatedData<KnowledgeBase>>> {
  return request.get('/api/v1/knowledge-bases', { params })
}

export function getKnowledgeBaseDetail(id: number): Promise<ApiResponse<KnowledgeBase>> {
  return request.get(`/api/v1/knowledge-bases/${id}`)
}

export function createKnowledgeBase(
  data: KnowledgeBaseCreateRequest,
): Promise<ApiResponse<KnowledgeBase>> {
  return request.post('/api/v1/knowledge-bases', data)
}

export function updateKnowledgeBase(
  id: number,
  data: KnowledgeBaseUpdateRequest,
): Promise<ApiResponse<KnowledgeBase>> {
  return request.put(`/api/v1/knowledge-bases/${id}`, data)
}

export function updateKnowledgeBaseStatus(
  id: number,
  data: KnowledgeBaseStatusRequest,
): Promise<ApiResponse<KnowledgeBase>> {
  return request.patch(`/api/v1/knowledge-bases/${id}/status`, data)
}
