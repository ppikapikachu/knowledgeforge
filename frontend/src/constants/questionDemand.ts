/**
 * 知识点重要程度、策略来源、分配模式 映射
 *
 * 依据：
 * - backend/app/services/knowledge_demand_service.py: IMPORTANCE_LEVELS
 * - backend/app/services/policy_service.py: source 值
 * - backend/app/schemas/question_demand.py: ImportanceLevel, ImportanceSource
 */

// ==================== 重要程度 ====================

export const IMPORTANCE_LEVELS = [
  { value: 'core', label: '核心必考', description: '基础主干、关键原理、必要前置概念', score: 1.0 },
  { value: 'important', label: '重点掌握', description: '重要机制、常见实践和关键限制', score: 0.75 },
  { value: 'normal', label: '常见考点', description: '常规且有学习价值的知识点', score: 0.5 },
  { value: 'supplementary', label: '扩展了解', description: '低频细节、边缘用法和补充内容', score: 0.25 },
] as const

export const IMPORTANCE_LABELS: Record<string, string> = {
  core: '核心必考',
  important: '重点掌握',
  normal: '常见考点',
  supplementary: '扩展了解',
}

export const IMPORTANCE_CLASSES: Record<string, string> = {
  core: 'error',
  important: 'warning',
  normal: 'success',
  supplementary: 'muted',
}

// ==================== 重要程度来源 ====================

export const IMPORTANCE_SOURCES = [
  { value: 'default', label: '系统默认' },
  { value: 'agent', label: 'AI 标注' },
  { value: 'manual', label: '管理员调整' },
] as const

export const IMPORTANCE_SOURCE_LABELS: Record<string, string> = {
  default: '系统默认',
  agent: 'AI 标注',
  manual: '管理员调整',
}

// ==================== 分配模式 ====================

export const ALLOCATION_MODE_LABELS: Record<string, string> = {
  manual: '指定知识点',
  auto: '系统智能分配',
}

// ==================== 策略来源（后端实际值） ====================

export const POLICY_SOURCE_LABELS: Record<string, string> = {
  global_default: '使用全局默认策略',
  question_bank_override: '使用题库独立策略',
}

// ==================== 策略字段约束（与后端 PolicyRequest 对齐） ====================

export const POLICY_CONSTRAINTS = {
  stock_weight: { min: 0, max: 100 },
  usage_weight: { min: 0, max: 100 },
  importance_weight: { min: 0, max: 100 },
  target_stock: { min: 1, max: 500 },
  usage_window_days: { min: 1, max: 365 },
  recent_answers_per_question_target: { min: 1, max: 100 },
  usage_extra_ratio: { min: 0, max: 2 },
  max_per_knowledge_per_task: { min: 1, max: 50 },
  min_demand_score: { min: 0, max: 1 },
} as const

// ==================== 通用工具 ====================

export function formatScore(score: number): string {
  return (score * 100).toFixed(1) + '%'
}

export function formatDateTime(dateStr: string | null | undefined): string {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}
