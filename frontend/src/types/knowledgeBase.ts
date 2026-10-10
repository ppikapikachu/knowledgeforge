export interface KnowledgeBase {
  id: number
  code: string
  name: string
  description: string | null
  status: number
  knowledge_count: number
  created_at: string
  updated_at: string
}

export interface KnowledgeBaseCreateRequest {
  code: string
  name: string
  description?: string | null
}

export interface KnowledgeBaseUpdateRequest {
  name?: string | null
  description?: string | null
}

export interface KnowledgeBaseStatusRequest {
  status: number
}

export interface KnowledgeBaseQueryParams {
  page?: number
  page_size?: number
  status?: number | null
}
