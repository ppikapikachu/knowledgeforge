import request from '@/utils/request'
import type { ApiResponse, PaginatedData } from '@/types/auth'
import type { ImportTask, ImportTaskQueryParams } from '@/types/importTask'

export function createImportTask(
  file: File,
  knowledgeBaseId: number,
): Promise<ApiResponse<{ task_id: number }>> {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('knowledge_base_id', String(knowledgeBaseId))
  return request.post('/api/v1/import-tasks', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  })
}

/**
 * 正式执行导入任务（提交后台执行，立即返回 ACCEPTED）
 * 响应 data: { task_id, status: "ACCEPTED", message }
 */
export function runImportTask(
  id: number,
): Promise<ApiResponse<{ task_id: number; status: string; message: string }>> {
  return request.post(`/api/v1/import-tasks/${id}/run`)
}

export function getImportTaskList(params: ImportTaskQueryParams): Promise<ApiResponse<PaginatedData<ImportTask>>> {
  return request.get('/api/v1/import-tasks', { params })
}

export function getImportTaskDetail(id: number): Promise<ApiResponse<ImportTask>> {
  return request.get(`/api/v1/import-tasks/${id}`)
}

export function simulateImportTask(id: number): Promise<ApiResponse<ImportTask>> {
  return request.post(`/api/v1/import-tasks/${id}/simulate`)
}
