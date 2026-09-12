import request from '@/utils/request'
import type { LoginRequest, LoginResponse, AdminUser, ApiResponse } from '@/types/auth'

export function login(data: LoginRequest): Promise<ApiResponse<LoginResponse>> {
  return request.post('/api/v1/auth/login', data)
}

export function getMe(): Promise<ApiResponse<AdminUser>> {
  return request.get('/api/v1/auth/me')
}
