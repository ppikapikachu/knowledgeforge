import request from '@/utils/request'
import type { ApiResponse, PaginatedData } from '@/types/auth'
import type {
  DedupStatusData,
  DedupRecord,
  DedupRecordQueryParams,
  TaskDedupStats,
  ResolveDedupRecordRequest,
  ResolveDedupRecordResponse,
} from '@/types/questionDedup'

/**
 * 获取去重服务状态
 * GET /api/v1/question-dedup/status
 */
export function getDedupStatus(): Promise<ApiResponse<DedupStatusData>> {
  return request.get('/api/v1/question-dedup/status')
}

/**
 * 查询去重判定审计记录
 * GET /api/v1/question-dedup/records
 * query: task_id, question_id, decision, needs_manual_review, page, page_size
 */
export function getDedupRecords(
  params: DedupRecordQueryParams,
): Promise<ApiResponse<PaginatedData<DedupRecord>>> {
  return request.get('/api/v1/question-dedup/records', { params })
}

/**
 * 任务去重统计
 * GET /api/v1/question-dedup/stats/{task_id}
 */
export function getTaskDedupStats(taskId: number): Promise<ApiResponse<TaskDedupStats>> {
  return request.get(`/api/v1/question-dedup/stats/${taskId}`)
}

/**
 * 手动重建题目向量索引
 * POST /api/v1/question-dedup/index/rebuild?only_missing=true
 * 返回 readiness 对象（同 /status）
 */
export function rebuildDedupIndex(
  onlyMissing = true,
): Promise<ApiResponse<DedupStatusData>> {
  return request.post(`/api/v1/question-dedup/index/rebuild?only_missing=${onlyMissing}`)
}

/**
 * 人工复核裁定
 * POST /api/v1/question-dedup/records/{record_id}/resolve
 * body: { conclusion: 'duplicate' | 'distinct', reason }
 */
export function resolveDedupRecord(
  recordId: number,
  payload: ResolveDedupRecordRequest,
): Promise<ApiResponse<ResolveDedupRecordResponse>> {
  return request.post(`/api/v1/question-dedup/records/${recordId}/resolve`, payload)
}
