import request from '@/utils/request'
import type { ApiResponse, PaginatedData } from '@/types/auth'
import type {
  AppUserListItem,
  AppUserQueryParams,
  UpdateAppUserStatusRequest,
  UpdateAppUserStatusResponse,
} from '@/types/appUser'

/**
 * 获取普通用户列表（管理员）
 * GET /api/v1/admin/app-users
 */
export function getAppUserList(
  params?: AppUserQueryParams,
): Promise<ApiResponse<PaginatedData<AppUserListItem>>> {
  return request.get('/api/v1/admin/app-users', { params })
}

/**
 * 获取普通用户详情（管理员）
 * GET /api/v1/admin/app-users/{id}
 */
export function getAppUserDetail(id: number): Promise<ApiResponse<AppUserListItem>> {
  return request.get(`/api/v1/admin/app-users/${id}`)
}

/**
 * 修改普通用户状态。
 * 禁用后后端会撤销该用户所有 Refresh 会话；历史学习数据仍保留。
 * 已删除用户不可恢复。
 */
export function updateAppUserStatus(
  id: number,
  payload: UpdateAppUserStatusRequest,
): Promise<ApiResponse<UpdateAppUserStatusResponse>> {
  return request.patch(`/api/v1/admin/app-users/${id}/status`, payload)
}
