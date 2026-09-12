import request from '@/utils/request'
import type { ApiResponse } from '@/types/auth'
import type { DashboardOverview } from '@/types/dashboard'

export function getDashboardOverview(): Promise<ApiResponse<DashboardOverview>> {
  return request.get('/api/v1/dashboard/overview')
}
