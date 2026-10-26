/**
 * AI 质量审核状态/结论/风险等级 映射
 * 依据：backend/app/api/v1/question_review.py、文档 §4.2 §5.3
 */

// ==================== 审核状态 ====================

export const AI_REVIEW_STATUS_LABELS: Record<string, string> = {
  not_requested: '未启用',
  queued: '等待审核',
  running: 'AI 审核中',
  completed: '审核完成',
  partial: '部分完成',
  failed: '审核失败',
}

export const AI_REVIEW_STATUS_CLASSES: Record<string, string> = {
  not_requested: 'muted',
  queued: 'info',
  running: 'info',
  completed: 'success',
  partial: 'warning',
  failed: 'error',
}

// ==================== 审核结论 ====================

export const AI_REVIEW_DECISION_LABELS: Record<string, string> = {
  auto_approve: 'AI 自动通过',
  auto_reject: 'AI 自动驳回',
  manual_review: '建议人工审核',
}

export const AI_REVIEW_DECISION_CLASSES: Record<string, string> = {
  auto_approve: 'success',
  auto_reject: 'error',
  manual_review: 'warning',
}

// ==================== 风险等级 ====================

export const AI_RISK_LEVEL_LABELS: Record<string, string> = {
  low: '低',
  medium: '中',
  high: '高',
  unknown: '未知',
}

export const AI_RISK_LEVEL_CLASSES: Record<string, string> = {
  low: 'success',
  medium: 'warning',
  high: 'error',
  unknown: 'muted',
}

// ==================== 执行状态 ====================

export const AI_EXECUTION_STATUS_LABELS: Record<string, string> = {
  success: '执行成功',
  failed: '执行失败',
  skipped: '已跳过',
}

export const AI_EXECUTION_STATUS_CLASSES: Record<string, string> = {
  success: 'success',
  failed: 'error',
  skipped: 'muted',
}

// ==================== 问题类型（已知枚举） ====================

export const ISSUE_TYPE_LABELS: Record<string, string> = {
  incorrect_answer: '答案错误',
  factual_error: '事实性错误',
  ambiguous_stem: '题干歧义',
  insufficient_context: '信息不足/上下文缺失',
  invalid_options: '选项无效/重复',
  multiple_correct_options: '多个正确选项（单选题）',
  no_correct_option: '没有正确选项',
  knowledge_mismatch: '与关联知识点不符',
  difficulty_mismatch: '难度标注不匹配',
  explanation_conflict: '解析与答案矛盾',
  version_ambiguity: '版本/环境依赖不清',
  outdated_content: '内容过时',
  other: '其他',
}

// ==================== 工具函数 ====================

export function getAiReviewStatusLabel(status: string | null | undefined): string {
  if (!status) return '未启用'
  return AI_REVIEW_STATUS_LABELS[status] || `未知状态（${status}）`
}

export function getAiReviewStatusClass(status: string | null | undefined): string {
  if (!status) return 'muted'
  return AI_REVIEW_STATUS_CLASSES[status] || 'muted'
}

export function getAiDecisionLabel(decision: string | null | undefined): string {
  if (!decision) return '无审核结论'
  return AI_REVIEW_DECISION_LABELS[decision] || `未知（${decision}）`
}

export function getAiDecisionClass(decision: string | null | undefined): string {
  if (!decision) return 'muted'
  return AI_REVIEW_DECISION_CLASSES[decision] || 'muted'
}

export function getRiskLevelLabel(level: string | null | undefined): string {
  if (!level) return '未知'
  return AI_RISK_LEVEL_LABELS[level] || `未知（${level}）`
}

export function getRiskLevelClass(level: string | null | undefined): string {
  if (!level) return 'muted'
  return AI_RISK_LEVEL_CLASSES[level] || 'muted'
}

export function getExecutionStatusLabel(status: string | null | undefined): string {
  if (!status) return '-'
  return AI_EXECUTION_STATUS_LABELS[status] || `未知（${status}）`
}

export function getExecutionStatusClass(status: string | null | undefined): string {
  if (!status) return 'muted'
  return AI_EXECUTION_STATUS_CLASSES[status] || 'muted'
}

/** 问题类型中文名（未知枚举安全回退） */
export function getIssueTypeLabel(issueType: string): string {
  return ISSUE_TYPE_LABELS[issueType] || `其他问题（${issueType}）`
}
