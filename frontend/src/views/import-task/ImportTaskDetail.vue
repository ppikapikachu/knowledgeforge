<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getImportTaskDetail, simulateImportTask } from '@/api/importTask'
import type { ImportTask } from '@/types/importTask'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  ArrowLeft,
  Play,
  CheckCircle,
  XCircle,
  Clock,
  Loader,
  AlertTriangle,
} from 'lucide-vue-next'

const route = useRoute()
const router = useRouter()
const loading = ref(true)
const task = ref<ImportTask | null>(null)
const simulating = ref(false)

const taskId = computed(() => Number(route.params.id))
let pollTimer: ReturnType<typeof setInterval> | null = null

const steps = [
  { key: 'UPLOADING', label: '文件上传' },
  { key: 'PARSING', label: '文件解析' },
  { key: 'EXTRACTING_KNOWLEDGE', label: '知识点提取' },
  { key: 'DEDUPLICATING', label: '去重处理' },
  { key: 'MERGING_KNOWLEDGE', label: '知识点合并' },
  { key: 'BUILDING_RELATIONS', label: '构建关系' },
  { key: 'GENERATING_QUESTIONS', label: '生成题目' },
  { key: 'EVALUATING_QUESTIONS', label: '评估题目' },
  { key: 'SAVING', label: '保存数据' },
  { key: 'FINISHED', label: '完成' },
]

async function fetchData() {
  try {
    const res = await getImportTaskDetail(taskId.value)
    task.value = res.data

    // Stop polling if task is completed
    if (['SUCCESS', 'PARTIAL_SUCCESS', 'FAILED', 'CANCELLED'].includes(task.value.status)) {
      stopPolling()
    }
  } catch {
    ElMessage.error('获取任务详情失败')
    stopPolling()
  } finally {
    loading.value = false
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

async function handleSimulate() {
  try {
    await ElMessageBox.confirm(
      '模拟执行将模拟任务的处理过程，是否继续？',
      '模拟执行',
      {
        confirmButtonText: '开始模拟',
        cancelButtonText: '取消',
        type: 'info',
      },
    )
    simulating.value = true
    await simulateImportTask(taskId.value)
    ElMessage.success('模拟已启动')
    startPolling()
  } catch {
    // Cancelled
  } finally {
    simulating.value = false
  }
}

function getStatusLabel(status: string) {
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

function getStatusClass(status: string) {
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

function getStepStatus(stepKey: string) {
  if (!task.value) return 'pending'
  const currentStep = task.value.current_step || ''
  const stepIndex = steps.findIndex((s) => s.key === stepKey)
  const currentIndex = steps.findIndex((s) => s.key === currentStep)

  if (task.value.status === 'SUCCESS') return 'completed'
  if (task.value.status === 'FAILED') {
    if (stepIndex < currentIndex) return 'completed'
    if (stepIndex === currentIndex) return 'failed'
    return 'pending'
  }
  if (stepIndex < currentIndex) return 'completed'
  if (stepIndex === currentIndex) return 'active'
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

onMounted(() => {
  fetchData().then(() => {
    // Start polling if task is running
    if (task.value && task.value.status === 'RUNNING') {
      startPolling()
    }
  })
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
        <el-button
          v-if="task && ['PENDING', 'FAILED'].includes(task.status)"
          type="primary"
          :loading="simulating"
          @click="handleSimulate"
        >
          <Play :size="16" style="margin-right: 4px;" />
          模拟执行
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
              <div v-if="task.current_step" class="current-step">
                当前步骤：{{ task.current_step }}
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
              :status="task.status === 'FAILED' ? 'exception' : undefined"
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
