export interface Knowledge {
  id: number
  name: string
  summary: string | null
  content: string | null
  difficulty: number
  status: number
  source_type: string
  source_document: string | null
  keywords: unknown[] | null
  question_count: number
  created_at: string
  updated_at: string
}

export interface KnowledgeCreateRequest {
  name: string
  summary?: string | null
  content?: string | null
  difficulty?: number
  status?: number
  source_type?: string
  source_document?: string | null
  keywords?: string[] | null
}

export interface KnowledgeUpdateRequest {
  name?: string | null
  summary?: string | null
  content?: string | null
  difficulty?: number | null
  status?: number | null
  source_type?: string | null
  source_document?: string | null
  keywords?: string[] | null
}

export interface KnowledgeRelation {
  id: number
  source_knowledge_id: number
  target_knowledge_id: number
  relation_type: string
  target_knowledge_name: string | null
  created_at: string
}

export interface KnowledgeRelationCreateRequest {
  target_knowledge_id: number
  relation_type: string
}

export interface KnowledgeQueryParams {
  page?: number
  page_size?: number
  keyword?: string | null
  difficulty?: number | null
  status?: number | null
}
