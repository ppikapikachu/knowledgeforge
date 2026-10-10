<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getImportTaskDetail, runImportTask } from '@/api/importTask'
import { getKnowledgeBaseDetail } from '@/api/knowledgeBase'
import type { ImportTask } from '@/types/importTask'
import {
  STEP_ORDER,
  STEP_LABELS,
  getStepLabel,
  isTerminalStatus,
  getStatusLabel,
  getStatusClass,
} from '@/constants/importTask'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  ArrowLeft,
  Play,
  CheckCircle,
  XCircle,
  Clock,
  Loader,
  AlertTriangle,
  RotateCcw,
} from 'lucide-vue-next'

const route = useRoute()
const router = useRouter()
const loading = ref(true)
const task = ref<ImportTask | null>(null)
const running = ref(false)   // /run 调用中
const kbName = ref('')

const taskId = computed(() => Number(route.params.id))

// 上传流程跳转时携带 started=1，表示 /run 已调用，不显示执行按钮
const autoStarted = ref(route.query.started === '1')

/**
 * 是否显示"执行/重新执行"按钮
 * - 仅 PENDING 且从未启动过（无 started_at、非自动启动）时显示"执行导入"
 * - FAILED / PARTIAL_SUCCESS 显示"重新执行"
 * - RUNNING / SUCCESS / CANCELLED 不显示
 */
const showRunButton = computed(() => {
  if (!task.value) return false
  const s = task.value.status
  if (s === 'FAILED' || s === 'PARTIAL_SUCCESS') return true
  if (s === 'PENDING' && !autoStarted.value && !task.value.started_at) return true
  return false
})

let pollTimer: ReturnType<typeof setInterval> | null = null
let isPolling = false  // 防止轮询请求重叠

// 处理阶段列表（顺序与后端 STAGE_* 一致）
const steps = STEP_ORDER.map((key) => ({ key, label: STEP_LABELS[key] || key }))

async function fetchData() {
  if (isPolling) return
  isPolling = true
  try {
    const res = await getImportTaskDetail(taskId.value)
    task.value = res.data

    // 加载知识库名称（仅一次）
    if (task.value?.knowledge_base_id && !kbName.value) {
      try {
        const kbRes = await getKnowledgeBaseDetail(task.value.knowledge_base_id)
        kbName.value = kbRes.data.name
      } catch {
        kbName.value = ''
      }
    }

    // 终态停止轮询
    if (isTerminalStatus(task.value.status)) {
      stopPolling()
    }
  } catch {
    ElMessage.error('获取任务详情失败')
    stopPolling()
  } finally {
    loading.value = false
    isPolling = false
  }
}

function startPolling() {
  stopPolling()
  pollTimer = setInterval(fetchData, 2000)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

/**
 * 调用正式执行接口 /run
 * 同一任务不得重复触发：调用期间禁用按钮
 */
async function handleRun() {
  if (running.value) return
  if (!task.value) return

  try {
    await ElMessageBox.confirm(
      '确认执行该导入任务？任务将在后台运行，可通过刷新页面查看进度。',
      '执行确认',
      {
        confirmButtonText: '开始执行',
        cancelButtonText: '取消',
        type: 'info',
      },
    )
  } catch {
    return
  }

  running.value = true
  try {
    const res = await runImportTask(taskId.value)
    // /run 返回 ACCEPTED，表示任务已提交后台
    autoStarted.value = true  // 防止按钮再次出现
    ElMessage.success(res.data?.message || '任务已提交，正在后台处理...')
    // 开始轮询
    await fetchData()
    if (task.value && !isTerminalStatus(task.value.status)) {
      startPolling()
    }
  } catch {
    // /run 失败，不假装任务已开始
    // 错误已由 axios 拦截器展示，此处提供重试入口（按钮仍在）
  } finally {
    running.value = false
  }
}

function getStatusIcon(status: string) {
  const map: Record<string, unknown> = {
    PENDING: Clock,
    RUNNING: Loader,
    SUCCESS: CheckCircle,
    PARTIAL_SUCCESS: AlertTriangle,
    FAILED: XCircle,
    CANCELLED: XCircle,
  }
  return map[status] || Clock
}

function getStepStatus(stepKey: string): 'completed' | 'active' | 'failed' | 'pending' {
  if (!task.value) return 'pending'
  const { status, current_step } = task.value
  const stepIdx = STEP_ORDER.indexOf(stepKey)
  const curIdx = current_step ? STEP_ORDER.indexOf(current_step) : -1

  // SUCCESS：全部完成
  if (status === 'SUCCESS') return 'completed'

  // FAILED
  if (status === 'FAILED') {
    if (curIdx === -1) {
      // 无法确定失败阶段，最后一步标记 failed
      return stepIdx === STEP_ORDER.length - 1 ? 'failed' : 'pending'
    }
    if (stepIdx < curIdx) return 'completed'
    if (stepIdx === curIdx) return 'failed'
    return 'pending'
  }

  // PARTIAL_SUCCESS 视为完成（结果有失败但流程结束）
  if (status === 'PARTIAL_SUCCESS') return 'completed'

  // PENDING / RUNNING
  if (curIdx === -1) return 'pending'
  if (stepIdx < curIdx) return 'completed'
  if (stepIdx === curIdx) return 'active'
  return 'pending'
}

function formatFileSize(bytes: number) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

function formatDate(dateStr: string | null) {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

onMounted(async () => {
  await fetchData()
  // RUNNING 或自动启动的任务，恢复轮询（不重复调用 /run）
  if (task.value && (task.value.status === 'RUNNING' || autoStarted.value)) {
    if (!isTerminalStatus(task.value.status)) {
      startPolling()
    }
  }
})

onUnmounted(() => {
  stopPolling()
})
</script>

<template>
  <div class="page-container">
    <div class="page-header">
      <div>
        <h2>任务详情</h2>
        <p class="description">查看导入任务的详细信息和处理进度</p>
      </div>
      <div style="display: flex; gap: 8px;">
        <el-button @click="router.back()">
          <ArrowLeft :size="16" style="margin-right: 4px;" />
          返回
        </el-button>
        <!-- 待执行 / 失败后重试 -->
        <el-button
          v-if="showRunButton"
          type="primary"
          :loading="running"
          @click="handleRun"
        >
          <RotateCcw v-if="task && task.status !== 'PENDING'" :size="16" style="margin-right: 4px;" />
          <Play v-else :size="16" style="margin-right: 4px;" />
          {{ task && task.status === 'PENDING' ? '执行导入' : '重新执行' }}
        </el-button>
      </div>
    </div>

    <div v-if="loading" class="card">
      <div class="card-body">
        <el-skeleton :rows="10" animated />
      </div>
    </div>

    <template v-else-if="task">
      <!-- File info -->
      <div class="card">
        <div class="card-header">文件信息</div>
        <div class="card-body">
          <el-descriptions :column="2" border>
            <el-descriptions-item label="文件名">
              {{ task.file_name }}
            </el-descriptions-item>
            <el-descriptions-item label="目标知识库">
              {{ kbName || '#' + task.knowledge_base_id }}
            </el-descriptions-item>
            <el-descriptions-item label="文件类型">
              {{ task.file_type }}
            </el-descriptions-item>
            <el-descriptions-item label="文件大小">
              {{ formatFileSize(task.file_size) }}
            </el-descriptions-item>
            <el-descriptions-item label="创建人ID">
              {{ task.created_by }}
            </el-descriptions-item>
            <el-descriptions-item label="创建时间">
              {{ formatDate(task.created_at) }}
            </el-descriptions-item>
            <el-descriptions-item label="开始时间">
              {{ formatDate(task.started_at) }}
            </el-descriptions-item>
            <el-descriptions-item label="完成时间">
              {{ formatDate(task.finished_at) }}
            </el-descriptions-item>
          </el-descriptions>
        </div>
      </div>

      <!-- Task status -->
      <div class="card" style="margin-top: 16px;">
        <div class="card-header">任务状态</div>
        <div class="card-body">
          <div class="task-status-section">
            <div class="status-icon-large" :class="`status-${getStatusClass(task.status)}`">
              <component :is="getStatusIcon(task.status)" :size="32" />
            </div>
            <div class="status-info">
              <div class="status-label">
                <span :class="['status-badge', `status-badge--${getStatusClass(task.status)}`]">
                  {{ getStatusLabel(task.status) }}
                </span>
              </div>
              <div class="current-step">
                <template v-if="task.current_step">
                  当前阶段：{{ getStepLabel(task.current_step) }}
                  <span class="step-raw" v-if="getStepLabel(task.current_step) !== task.current_step">
                    ({{ task.current_step }})
                  </span>
                </template>
                <template v-else-if="task.status === 'PENDING'">
                  等待执行
                </template>
                <template v-else>
                  —
                </template>
              </div>
            </div>
          </div>

          <!-- Progress -->
          <div class="progress-section" style="margin-top: 24px;">
            <div class="progress-header">
              <span>处理进度</span>
              <span class="progress-value">{{ task.progress }}%</span>
            </div>
            <el-progress
              :percentage="task.progress"
              :stroke-width="12"
              :status="task.status === 'FAILED' ? 'exception' : (task.status === 'SUCCESS' ? 'success' : undefined)"
            />
          </div>
        </div>
      </div>

      <!-- Processing steps -->
      <div class="card" style="margin-top: 16px;">
        <div class="card-header">处理阶段</div>
        <div class="card-body">
          <div class="steps-list">
            <div
              v-for="step in steps"
              :key="step.key"
              class="step-item"
              :class="`step-${getStepStatus(step.key)}`"
            >
              <div class="step-icon">
                <CheckCircle v-if="getStepStatus(step.key) === 'completed'" :size="20" />
                <Loader v-else-if="getStepStatus(step.key) === 'active'" :size="20" class="spin" />
                <XCircle v-else-if="getStepStatus(step.key) === 'failed'" :size="20" />
                <Clock v-else :size="20" />
              </div>
              <div class="step-label">{{ step.label }}</div>
            </div>
          </div>
        </div>
      </div>

      <!-- Error message -->
      <div v-if="task.error_message" class="card" style="margin-top: 16px;">
        <div class="card-header" style="color: var(--color-error);">错误信息</div>
        <div class="card-body">
          <div class="error-message">{{ task.error_message }}</div>
        </div>
      </div>
    </template>

    <!-- Error -->
    <div v-else class="card">
      <div class="empty-state">
        <p class="title">任务不存在</p>
        <el-button type="primary" @click="router.push('/import-tasks')">返回列表</el-button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.task-status-section {
  display: flex;
  align-items: center;
  gap: 16px;
}

.status-icon-large {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.status-icon-large.status-success {
  background: #ECFDF5;
  color: var(--color-success);
}

.status-icon-large.status-info {
  background: #EFF6FF;
  color: var(--color-info);
}

.status-icon-large.status-warning {
  background: #FFFBEB;
  color: var(--color-warning);
}

.status-icon-large.status-error {
  background: #FEF2F2;
  color: var(--color-error);
}

.status-icon-large.status-muted {
  background: var(--color-muted);
  color: var(--color-muted-foreground);
}

.status-label {
  font-size: 18px;
  font-weight: 600;
  margin-bottom: 4px;
}

.current-step {
  font-size: 14px;
  color: var(--color-muted-foreground);
}

.step-raw {
  font-size: 12px;
  color: var(--color-muted-foreground);
  opacity: 0.7;
  margin-left: 4px;
}

.progress-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
  font-size: 14px;
  color: var(--color-muted-foreground);
}

.progress-value {
  font-weight: 600;
  color: var(--color-foreground);
}

.steps-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.step-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border-radius: var(--radius-md);
  background: var(--color-muted);
}

.step-item.step-completed {
  background: #ECFDF5;
}

.step-item.step-active {
  background: #EFF6FF;
  border: 1px solid var(--color-info);
}

.step-item.step-failed {
  background: #FEF2F2;
}

.step-icon {
  flex-shrink: 0;
  color: var(--color-muted-foreground);
}

.step-completed .step-icon {
  color: var(--color-success);
}

.step-active .step-icon {
  color: var(--color-info);
}

.step-failed .step-icon {
  color: var(--color-error);
}

.step-label {
  font-size: 14px;
  font-weight: 500;
}

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.error-message {
  padding: 16px;
  background: #FEF2F2;
  border-radius: var(--radius-md);
  color: var(--color-error);
  font-size: 14px;
  white-space: pre-wrap;
}
</style>
