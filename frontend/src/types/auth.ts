export interface LoginRequest {
  username: string
  password: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
}

export interface AdminUser {
  id: number
  username: string
  nickname: string
  avatar: string | null
  status: number
  last_login_at: string | null
  created_at: string
}

export interface ApiResponse<T = unknown> {
  code: number
  message: string
  data: T
}

export interface PaginatedData<T> {
  items: T[]
  page: number
  page_size: number
  total: number
}
