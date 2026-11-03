/**
 * 普通用户状态映射
 * 依据：backend/app/api/v1/admin_app_users.py
 */

export const APP_USER_STATUS_LABELS: Record<string, string> = {
  active: '正常',
  disabled: '已禁用',
  deleted: '已删除',
}

export const APP_USER_STATUS_CLASSES: Record<string, string> = {
  active: 'success',
  disabled: 'warning',
  deleted: 'muted',
}

export function getAppUserStatusLabel(status: string): string {
  return APP_USER_STATUS_LABELS[status] || status
}

export function getAppUserStatusClass(status: string): string {
  return APP_USER_STATUS_CLASSES[status] || 'muted'
}
