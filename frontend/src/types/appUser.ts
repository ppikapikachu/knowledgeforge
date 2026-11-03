/**
 * 普通用户管理类型定义
 * 依据：backend/app/api/v1/admin_app_users.py、app/models/app_user.py
 * 安全约束：后端响应不含 password_hash / refresh_token_hash，前端也不得引入。
 */

// ==================== 枚举 ====================

export type AppUserStatus = 'active' | 'disabled' | 'deleted'

// ==================== 列表项 ====================

export interface AppUserListItem {
  id: number
  account: string
  nickname: string | null
  avatar: string | null
  status: AppUserStatus
  last_login_at: string | null
  deleted_at: string | null
  active_session_count: number
  created_at: string | null
}

export interface AppUserQueryParams {
  keyword?: string | null
  status?: AppUserStatus | null
  page?: number
  page_size?: number
}

// ==================== 状态变更 ====================

export interface UpdateAppUserStatusRequest {
  /** 仅允许 active 或 disabled，deleted 为终态不可修改 */
  status: 'active' | 'disabled'
  /** 管理员执行状态变更的原因 */
  reason: string
}

export interface UpdateAppUserStatusResponse {
  id: number
  status: AppUserStatus
  /** 本次操作撤销的 refresh 会话数量 */
  revoked_sessions: number
}
