/**
 * AI 批量审核状态/原因码 中文映射
 * 依据：backend/app/services/question_review_batch_service.py 的 _reason_text + 状态枚举
 */

// ==================== 批次状态 ====================

export const BATCH_STATUS_LABELS: Record<string, string> = {
  queued: '排队中',
  running: '审核中',
  completed: '已完成',
  partial: '部分完成',
  failed: '执行失败',
  cancelled: '已取消',
}

export const BATCH_STATUS_CLASSES: Record<string, string> = {
  queued: 'info',
  running: 'warning',
  completed: 'success',
  partial: 'warning',
  failed: 'error',
  cancelled: 'muted',
}

// ==================== 批次 item 状态 ====================

export const BATCH_ITEM_STATUS_LABELS: Record<string, string> = {
  queued: '等待审核',
  running: '正在审核',
  completed: '审核完成',
  failed: '审核失败',
  skipped: '已跳过',
}

export const BATCH_ITEM_STATUS_CLASSES: Record<string, string> = {
  queued: 'info',
  running: 'warning',
  completed: 'success',
  failed: 'error',
  skipped: 'muted',
}

// ==================== 跳过原因码 ====================

export const SKIP_REASON_LABELS: Record<string, string> = {
  question_not_found: '题目不存在或已被删除',
  question_not_pending: '题目已不处于待审核状态',
  unsupported_question_type: '当前题型暂不支持 AI 审核（如简答题）',
  dedup_unresolved: '存在尚未处理的去重疑点',
  dedup_duplicate: '去重结论为重复，不允许进入 AI 审核',
  concurrent_review_in_progress: '该题正在被其他审核任务处理',
}

export function getSkipReasonLabel(reasonCode: string | null | undefined): string {
  if (!reasonCode) return ''
  return SKIP_REASON_LABELS[reasonCode] || `未知原因（${reasonCode}）`
}

// ==================== 状态工具 ====================

export function getBatchStatusLabel(status: string): string {
  return BATCH_STATUS_LABELS[status] || `未知状态（${status}）`
}

export function getBatchStatusClass(status: string): string {
  return BATCH_STATUS_CLASSES[status] || 'muted'
}

export function getBatchItemStatusLabel(status: string): string {
  return BATCH_ITEM_STATUS_LABELS[status] || `未知状态（${status}）`
}

export function getBatchItemStatusClass(status: string): string {
  return BATCH_ITEM_STATUS_CLASSES[status] || 'muted'
}

export function isBatchTerminal(status: string): boolean {
  return ['completed', 'partial', 'failed', 'cancelled'].includes(status)
}

export function isBatchRunning(status: string): boolean {
  return status === 'queued' || status === 'running'
}
