/**
 * API 统一错误对象与业务码常量
 * 依据：后端统一响应信封 { code, message, data }
 */

export class ApiError extends Error {
  code: number
  data?: unknown
  httpStatus?: number

  constructor(message: string, code: number, data?: unknown, httpStatus?: number) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.data = data
    this.httpStatus = httpStatus
  }
}

export const API_CODE = {
  SUCCESS: 0,
  BUSINESS_ERROR: 40000,
  VALIDATION_ERROR: 40001,
  UNAUTHORIZED: 40101,
  FORBIDDEN: 40301,
  NOT_FOUND: 40401,
  CONFLICT: 40901,
  PARAM_ERROR: 42201,
  SERVER_ERROR: 50000,
} as const

export function isApiError(e: unknown): e is ApiError {
  return e instanceof ApiError
}
