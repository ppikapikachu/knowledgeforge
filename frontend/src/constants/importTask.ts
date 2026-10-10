/**
 * 导入任务状态与处理阶段映射
 *
 * 数据来源：backend/app/services/knowledge_import_service.py
 *   STAGE_PARSING         = "PARSING"
 *   STAGE_EXTRACTING      = "EXTRACTING_KNOWLEDGE"
 *   STAGE_DEDUPLICATING   = "DEDUPLICATING_KNOWLEDGE"
 *   STAGE_SAVING          = "SAVING_KNOWLEDGE"
 *   STAGE_SYNCING         = "SYNCING_EMBEDDINGS"
 *   STAGE_RELATIONS       = "BUILDING_RELATIONS"
 *   终态 "FINISHED" / "FAILED"
 *
 * 状态：backend/app/models/import_task.py
 *   PENDING / RUNNING / SUCCESS / PARTIAL_SUCCESS / FAILED / CANCELLED
 */

// ==================== 任务状态 ====================

export const TASK_STATUS = {
  PENDING: 'PENDING',
  RUNNING: 'RUNNING',
  SUCCESS: 'SUCCESS',
  PARTIAL_SUCCESS: 'PARTIAL_SUCCESS',
  FAILED: 'FAILED',
  CANCELLED: 'CANCELLED',
} as const

export type TaskStatus = (typeof TASK_STATUS)[keyof typeof TASK_STATUS]

/** 终态列表：进入后应停止轮询 */
export const TERMINAL_STATUSES: readonly string[] = [
  TASK_STATUS.SUCCESS,
  TASK_STATUS.PARTIAL_SUCCESS,
  TASK_STATUS.FAILED,
  TASK_STATUS.CANCELLED,
]

/** 判断是否为终态 */
export function isTerminalStatus(status: string): boolean {
  return TERMINAL_STATUSES.includes(status)
}

export function getStatusLabel(status: string): string {
  const map: Record<string, string> = {
    PENDING: '待处理',
    RUNNING: '运行中',
    SUCCESS: '成功',
    PARTIAL_SUCCESS: '部分成功',
    FAILED: '失败',
    CANCELLED: '已取消',
  }
  return map[status] || status
}

export function getStatusClass(status: string): string {
  const map: Record<string, string> = {
    PENDING: 'muted',
    RUNNING: 'info',
    SUCCESS: 'success',
    PARTIAL_SUCCESS: 'warning',
    FAILED: 'error',
    CANCELLED: 'muted',
  }
  return map[status] || 'muted'
}

// ==================== 处理阶段 ====================

/**
 * 后端 current_step 真实值 → 中文展示名
 */
export const STEP_LABELS: Record<string, string> = {
  PARSING: '解析文件',
  EXTRACTING_KNOWLEDGE: '提取知识点',
  DEDUPLICATING_KNOWLEDGE: '去重判断',
  SAVING_KNOWLEDGE: '保存知识点',
  SYNCING_EMBEDDINGS: '同步向量索引',
  BUILDING_RELATIONS: '生成知识关系',
  FINISHED: '完成',
  FAILED: '失败',
}

/**
 * 阶段展示顺序（用于进度步骤条）
 */
export const STEP_ORDER: string[] = [
  'PARSING',
  'EXTRACTING_KNOWLEDGE',
  'DEDUPLICATING_KNOWLEDGE',
  'SAVING_KNOWLEDGE',
  'SYNCING_EMBEDDINGS',
  'BUILDING_RELATIONS',
  'FINISHED',
]

/**
 * 获取阶段中文名；未知阶段返回兜底文案
 */
export function getStepLabel(step: string | null | undefined): string {
  if (!step) return '等待中'
  return STEP_LABELS[step] || `处理中（${step}）`
}

/**
 * 获取阶段在进度条中的索引，未知返回 -1
 */
export function getStepIndex(step: string | null | undefined): number {
  if (!step) return -1
  return STEP_ORDER.indexOf(step)
}

/**
 * 判断某阶段在指定任务状态下应显示的状态
 * 返回 'completed' | 'active' | 'failed' | 'pending'
 */
export function getStepStatus(
  stepKey: string,
  taskStatus: string,
  currentStep: string | null | undefined,
): 'completed' | 'active' | 'failed' | 'pending' {
  const stepIdx = STEP_ORDER.indexOf(stepKey)
  const curIdx = currentStep ? STEP_ORDER.indexOf(currentStep) : -1

  // 终态：SUCCESS
  if (taskStatus === TASK_STATUS.SUCCESS) {
    return 'completed'
  }

  // 终态：FAILED
  if (taskStatus === TASK_STATUS.FAILED) {
    if (currentStep === 'FAILED' || curIdx === -1) {
      // 未能确定具体失败阶段，标记所有为 pending，最后一个 active
      return stepIdx === STEP_ORDER.length - 2 ? 'failed' : 'pending'
    }
    if (stepIdx < curIdx) return 'completed'
    if (stepIdx === curIdx) return 'failed'
    return 'pending'
  }

  // 运行中 / PENDING
  if (curIdx === -1) return 'pending'
  if (stepIdx < curIdx) return 'completed'
  if (stepIdx === curIdx) return 'active'
  return 'pending'
}
