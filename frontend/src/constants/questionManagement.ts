/**
 * 题库管理模块：题型 / 难度 / 题目状态 / 任务状态 映射
 *
 * 全部取值来自后端真实代码：
 * - 题型与难度校验：backend/app/api/v1/question_generation.py
 *   question_type in ("SINGLE_CHOICE","MULTIPLE_CHOICE","TRUE_FALSE","SHORT_ANSWER")
 *   difficulty in (1,2,3)；schemas/question.py 注释：1=简单 2=中等 3=困难
 * - 题目状态：backend/app/models/question.py
 *   status comment = "pending_review/published/disabled/rejected"，default="pending_review"
 * - 任务状态：backend/app/models/question_generation_task.py
 *   status comment = "pending/running/partial_success/success/failed/cancelled"
 */

// ==================== 题型 ====================

export const QUESTION_TYPES = [
  { value: 'SINGLE_CHOICE', label: '单选题' },
  { value: 'MULTIPLE_CHOICE', label: '多选题' },
  { value: 'TRUE_FALSE', label: '判断题' },
  { value: 'SHORT_ANSWER', label: '简答题' },
] as const

export const QUESTION_TYPE_LABELS: Record<string, string> = Object.fromEntries(
  QUESTION_TYPES.map((t) => [t.value, t.label]),
)

/** 是否为选项类题型 */
export function isChoiceType(type: string): boolean {
  return type === 'SINGLE_CHOICE' || type === 'MULTIPLE_CHOICE'
}

// ==================== 难度 ====================

export const DIFFICULTIES = [
  { value: 1, label: '简单' },
  { value: 2, label: '中等' },
  { value: 3, label: '困难' },
] as const

export const DIFFICULTY_LABELS: Record<number, string> = {
  1: '简单',
  2: '中等',
  3: '困难',
}

export const DIFFICULTY_CLASSES: Record<number, string> = {
  1: 'easy',
  2: 'medium',
  3: 'hard',
}

// ==================== 题目状态 ====================

export const QUESTION_STATUS = {
  PENDING_REVIEW: 'pending_review',
  PUBLISHED: 'published',
  REJECTED: 'rejected',
  DISABLED: 'disabled',
} as const

export const QUESTION_STATUSES = [
  { value: 'pending_review', label: '待审核' },
  { value: 'published', label: '已发布' },
  { value: 'rejected', label: '已驳回' },
  { value: 'disabled', label: '已下架' },
] as const

export const QUESTION_STATUS_LABELS: Record<string, string> = {
  pending_review: '待审核',
  published: '已发布',
  rejected: '已驳回',
  disabled: '已下架',
}

export const QUESTION_STATUS_CLASSES: Record<string, string> = {
  pending_review: 'warning',
  published: 'success',
  rejected: 'error',
  disabled: 'muted',
}

/**
 * 题目状态归一化。
 * 后端存在大小写不一致：生成/审核写入小写（pending_review/published/rejected），
 * 而 question_repository.disable() 写入大写 "DISABLED"。
 * 前端做大小写容错匹配，但不修改、不掩盖服务端返回的原始值。
 */
export function normalizeQuestionStatus(status: string): string {
  return (status || '').toLowerCase()
}

export function questionStatusLabel(status: string): string {
  return QUESTION_STATUS_LABELS[normalizeQuestionStatus(status)] || status
}

export function questionStatusClass(status: string): string {
  return QUESTION_STATUS_CLASSES[normalizeQuestionStatus(status)] || 'muted'
}

// ==================== 生成任务状态 ====================

export const TASK_STATUSES = [
  { value: 'pending', label: '等待执行' },
  { value: 'running', label: '执行中' },
  { value: 'success', label: '全部成功' },
  { value: 'partial_success', label: '部分成功' },
  { value: 'failed', label: '生成失败' },
  { value: 'cancelled', label: '已取消' },
] as const

export const TASK_STATUS_LABELS: Record<string, string> = {
  pending: '等待执行',
  running: '执行中',
  success: '全部成功',
  partial_success: '部分成功',
  failed: '生成失败',
  cancelled: '已取消',
}

export const TASK_STATUS_CLASSES: Record<string, string> = {
  pending: 'muted',
  running: 'info',
  success: 'success',
  partial_success: 'warning',
  failed: 'error',
  cancelled: 'muted',
}

/** 任务终态：停止轮询 */
export function isTaskTerminal(status: string): boolean {
  return ['success', 'partial_success', 'failed', 'cancelled'].includes(status)
}

// ==================== 通用工具 ====================

export function truncateText(text: string | null | undefined, maxLen: number): string {
  if (!text) return '-'
  return text.length > maxLen ? text.slice(0, maxLen) + '…' : text
}

export function formatDateTime(dateStr: string | null | undefined): string {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}
