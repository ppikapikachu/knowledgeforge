import request from '@/utils/request'
import type { ApiResponse, PaginatedData } from '@/types/auth'
import type { ImportTask, ImportTaskQueryParams } from '@/types/importTask'

export function createImportTask(file: File): Promise<ApiResponse<ImportTask>> {
  const formData = new FormData()
  formData.append('file', file)
  return request.post('/api/v1/import-tasks', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  })
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
