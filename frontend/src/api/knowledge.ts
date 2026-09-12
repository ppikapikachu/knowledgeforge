import request from '@/utils/request'
import type { ApiResponse, PaginatedData } from '@/types/auth'
import type {
  Knowledge,
  KnowledgeCreateRequest,
  KnowledgeUpdateRequest,
  KnowledgeRelation,
  KnowledgeRelationCreateRequest,
  KnowledgeQueryParams,
} from '@/types/knowledge'

export function getKnowledgeList(params: KnowledgeQueryParams): Promise<ApiResponse<PaginatedData<Knowledge>>> {
  return request.get('/api/v1/knowledge', { params })
}

export function getKnowledgeDetail(id: number): Promise<ApiResponse<Knowledge>> {
  return request.get(`/api/v1/knowledge/${id}`)
}

export function createKnowledge(data: KnowledgeCreateRequest): Promise<ApiResponse<Knowledge>> {
  return request.post('/api/v1/knowledge', data)
}

export function updateKnowledge(id: number, data: KnowledgeUpdateRequest): Promise<ApiResponse<Knowledge>> {
  return request.put(`/api/v1/knowledge/${id}`, data)
}

export function deleteKnowledge(id: number): Promise<ApiResponse<null>> {
  return request.delete(`/api/v1/knowledge/${id}`)
}

export function getKnowledgeRelations(id: number): Promise<ApiResponse<KnowledgeRelation[]>> {
  return request.get(`/api/v1/knowledge/${id}/relations`)
}

export function createKnowledgeRelation(
  id: number,
  data: KnowledgeRelationCreateRequest,
): Promise<ApiResponse<KnowledgeRelation>> {
  return request.post(`/api/v1/knowledge/${id}/relations`, data)
}

export function deleteKnowledgeRelation(id: number, relationId: number): Promise<ApiResponse<null>> {
  return request.delete(`/api/v1/knowledge/${id}/relations/${relationId}`)
}
