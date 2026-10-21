/**
 * 题目去重状态/判定/方法 映射
 * 依据：backend/app/services/question_dedup_service.py、models/question_dedup_record.py
 */

// ==================== 索引服务状态 ====================

export const DEDUP_STATUS_LABELS: Record<string, string> = {
  ready: '语义去重正常',
  initializing: '语义去重索引正在初始化',
  degraded: '语义去重服务降级，语义查重能力可能不可用',
  disabled: '语义去重已关闭',
}

export const DEDUP_STATUS_CLASSES: Record<string, string> = {
  ready: 'success',
  initializing: 'info',
  degraded: 'error',
  disabled: 'muted',
}

// ==================== 判定结论 ====================

export const DEDUP_DECISION_LABELS: Record<string, string> = {
  duplicate: '确认重复',
  distinct: '不重复',
  uncertain: '待人工复核',
}

export const DEDUP_DECISION_CLASSES: Record<string, string> = {
  duplicate: 'error',
  distinct: 'success',
  uncertain: 'warning',
}

// ==================== 判定方式 ====================

export const DEDUP_METHOD_LABELS: Record<string, string> = {
  exact_hash: '指纹精确匹配',
  algorithm_only: '算法分数判定',
  vector_and_llm: '向量 + LLM 复核',
  batch_internal: '批次内比对',
}

// ==================== 范围模式 ====================

export const SCOPE_MODE_LABELS: Record<string, string> = {
  same_scope: '同知识范围',
  cross_scope: '跨范围',
  global_exact: '全局精确',
  batch_internal: '批次内',
}

// ==================== 任务去重复核状态 ====================

export const TASK_DEDUP_REVIEW_LABELS: Record<string, string> = {
  manual_review_required: '需人工复核',
  deduplicated: '有判重',
  clean: '无重复',
}

export const TASK_DEDUP_REVIEW_CLASSES: Record<string, string> = {
  manual_review_required: 'warning',
  deduplicated: 'info',
  clean: 'success',
}

// ==================== 题目去重复核状态 ====================

export const QUESTION_DEDUP_STATUS_LABELS: Record<string, string> = {
  none: '无疑点',
  distinct: '不重复',
  duplicate: '确认重复',
  uncertain: '待人工复核',
}

export const QUESTION_DEDUP_STATUS_CLASSES: Record<string, string> = {
  none: 'muted',
  distinct: 'success',
  duplicate: 'error',
  uncertain: 'warning',
}

// ==================== 人工裁定 ====================

export const MANUAL_RESOLUTION_LABELS: Record<string, string> = {
  duplicate: '人工确认重复',
  distinct: '人工确认不重复',
}

export const MANUAL_RESOLUTION_CLASSES: Record<string, string> = {
  duplicate: 'error',
  distinct: 'success',
}

// ==================== 工具函数 ====================

export function formatScore(score: number | null | undefined): string {
  if (score === null || score === undefined) return '-'
  return score.toFixed(4)
}

export function formatPercent(score: number | null | undefined): string {
  if (score === null || score === undefined) return '-'
  return (score * 100).toFixed(1) + '%'
}

export function getDedupStatusLabel(status: string): string {
  return DEDUP_STATUS_LABELS[status] || `未知状态（${status}）`
}

export function getDedupStatusClass(status: string): string {
  return DEDUP_STATUS_CLASSES[status] || 'muted'
}

export function getDecisionLabel(decision: string): string {
  return DEDUP_DECISION_LABELS[decision] || `未知（${decision}）`
}

export function getDecisionClass(decision: string): string {
  return DEDUP_DECISION_CLASSES[decision] || 'muted'
}

export function getMethodLabel(method: string): string {
  return DEDUP_METHOD_LABELS[method] || `未知（${method}）`
}

export function getScopeModeLabel(mode: string | null): string {
  if (!mode) return '-'
  return SCOPE_MODE_LABELS[mode] || mode
}

export function getTaskDedupReviewLabel(status: string): string {
  return TASK_DEDUP_REVIEW_LABELS[status] || status
}

export function getQuestionDedupStatusLabel(status: string): string {
  return QUESTION_DEDUP_STATUS_LABELS[status] || status
}

export function getManualResolutionLabel(resolution: string | null): string {
  if (!resolution) return ''
  return MANUAL_RESOLUTION_LABELS[resolution] || resolution
}

export function getManualResolutionClass(resolution: string | null): string {
  if (!resolution) return 'muted'
  return MANUAL_RESOLUTION_CLASSES[resolution] || 'muted'
}
