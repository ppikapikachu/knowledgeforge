export interface QuestionOption {
  id?: number
  question_id?: number
  option_key: string
  option_content: string
  is_correct: number
  sort_order: number
  created_at?: string
}

export interface Question {
  id: number
  question_bank_id: number
  question_type: string
  content: string
  answer: string
  analysis: string | null
  difficulty: number
  status: string
  source_type: string
  quality_score: string | null
  used_count: number
  correct_count: number
  options: QuestionOption[]
  knowledge_ids: number[]
  created_at: string
  updated_at: string
}

export interface QuestionCreateRequest {
  question_type: string
  content: string
  answer: string
  analysis?: string | null
  difficulty?: number
  status?: string
  source_type?: string
  quality_score?: number | null
  options?: QuestionOption[]
  knowledge_ids?: number[] | null
}

export interface QuestionUpdateRequest {
  question_type?: string | null
  content?: string | null
  answer?: string | null
  analysis?: string | null
  difficulty?: number | null
  status?: string | null
  source_type?: string | null
  quality_score?: number | null
  options?: QuestionOption[] | null
  knowledge_ids?: number[] | null
}

export interface QuestionQueryParams {
  page?: number
  page_size?: number
  keyword?: string | null
  question_type?: string | null
  difficulty?: number | null
  status?: string | null
  source_type?: string | null
  knowledge_id?: number | null
  question_bank_id?: number | null
}
