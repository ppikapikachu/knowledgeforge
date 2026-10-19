<script setup lang="ts">
/**
 * 生成任务详情
 * GET /api/v1/question-generation/tasks/{id}
 * 真实字段：task_id, created_by, status, request_config, total_count, success_count,
 * duplicate_count, failed_count, progress, error_summary, started_at, completed_at,
 * created_at, questions[]
 *
 * 轮询：仅 pending/running，间隔 3s；离开页面清理；终态停止。
 * 不修改后端返回的状态，不提供自动重试（后端无重试契约）。
 */
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getGenerationTaskDetail } from '@/api/questionGeneration'
import { useQuestionLookups } from '@/composables/useQuestionLookups'
import type { GenerationTaskDetail } from '@/types/questionManagement'
import {
  TASK_STATUS_LABELS,
  QUESTION_TYPE_LABELS,
  DIFFICULTY_LABELS,
  QUESTION_STATUS_LABELS,
  isTaskTerminal,
  formatDateTime,
} from '@/constants/questionManagement'
import TaskStatusTag from '@/components/question-management/TaskStatusTag.vue'
import QuestionStatusTag from '@/components/question-management/QuestionStatusTag.vue'
import { ElMessage } from 'element-plus'
import {
  ArrowLeft,
  RefreshCw,
  ExternalLink,
  ClipboardList,
  AlertTriangle,
} from 'lucide-vue-next'

const route = useRoute()
const router = useRouter()
const { loadAll, bankName, knowledgeName } = useQuestionLookups()

const loading = ref(true)
const task = ref<GenerationTaskDetail | null>(null)
const loadError = ref(false)

const taskId = computed(() => Number(route.params.taskId))
let pollTimer: ReturnType<typeof setInterval> | null = null
let polling = false // 防止请求重叠

const config = computed(() => task.value?.request_config || {})

function cfgNumber(key: string): number | undefined {
  const v = config.value[key]
  return typeof v === 'number' ? v : undefined
}

const bankLabel = computed(() => {
  const id = cfgNumber('question_bank_id')
  return id ? bankName(id) : '-'
})

const knowledgeLabel = computed(() => {
  const id = cfgNumber('knowledge_id')
  return id ? knowledgeName(id) : '-'
})

const typeLabel = computed(() => {
  const t = config.value.question_type
  return typeof t === 'string' ? QUESTION_TYPE_LABELS[t] || t : '-'
})

const difficultyLabel = computed(() => {
  const d = cfgNumber('difficulty')
  return d ? DIFFICULTY_LABELS[d] || String(d) : '-'
})

async function fetchData() {
  if (polling) return
  polling = true
  try {
    const res = await getGenerationTaskDetail(taskId.value)
    task.value = res.data
    loadError.value = false
    if (isTaskTerminal(res.data.status)) {
      stopPolling()
    }
  } catch {
    loadError.value = true
    stopPolling()
  } finally {
    loading.value = false
    polling = false
  }
}

function startPolling() {
  stopPolling()
  pollTimer = setInterval(fetchData, 3000)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

function handleManualRefresh() {
  fetchData()
}

function goToReview(qId: number) {
  router.push(`/question-management/review?question_id=${qId}`)
}

function goToList() {
  router.push('/question-management/questions')
}

onMounted(async () => {
  await Promise.all([loadAll(), fetchData()])
  if (task.value && !isTaskTerminal(task.value.status)) {
    startPolling()
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
        <h2>生成任务详情</h2>
        <p class="description">任务 #{{ taskId }}</p>
      </div>
      <div class="header-actions">
        <el-button @click="handleManualRefresh">
          <RefreshCw :size="16" style="margin-right: 4px;" />
          刷新
        </el-button>
        <el-button @click="router.push('/question-management/tasks')">
          <ClipboardList :size="16" style="margin-right: 4px;" />
          任务列表
        </el-button>
      </div>
    </div>

    <!-- 错误状态 -->
    <div v-if="loadError && !task" class="card">
      <div class="empty-state">
        <p class="title">任务加载失败</p>
        <p class="description">无法获取任务信息，请确认任务是否存在或后端服务正常</p>
        <el-button type="primary" @click="fetchData">重新加载</el-button>
        <el-button @click="router.push('/question-management/tasks')">返回任务列表</el-button>
      </div>
    </div>

    <!-- Loading -->
    <div v-else-if="loading" class="card">
      <div class="card-body">
        <el-skeleton :rows="8" animated />
      </div>
    </div>

    <template v-else-if="task">
      <!-- 基本信息 -->
      <div class="card">
        <div class="card-header">
          任务状态
          <el-button text type="primary" size="small" style="margin-left: 12px;" @click="router.push('/question-management/tasks')">
            <ArrowLeft :size="14" style="margin-right: 4px;" />
            返回列表
          </el-button>
        </div>
        <div class="card-body">
          <div class="status-row">
            <TaskStatusTag :status="task.status" />
            <span class="status-text">当前状态：{{ TASK_STATUS_LABELS[task.status] || task.status }}</span>
          </div>

          <!-- 进度 -->
          <div class="progress-block">
            <div class="progress-label">
              <span>生成进度</span>
              <span class="progress-value">{{ task.progress }}%</span>
            </div>
            <el-progress
              :percentage="task.progress"
              :stroke-width="12"
              :status="task.status === 'failed' ? 'exception' : (isTaskTerminal(task.status) ? 'success' : undefined)"
            />
            <div class="counts-row">
              <span>计划 <b>{{ task.total_count }}</b></span>
              <span class="ok">成功 <b>{{ task.success_count }}</b></span>
              <span class="dup">去重跳过 <b>{{ task.duplicate_count }}</b></span>
              <span class="fail">失败 <b>{{ task.failed_count }}</b></span>
            </div>
          </div>

          <!-- running 长时间无进度提示 -->
          <div v-if="task.status === 'running'" class="hint-block">
            任务仍处于执行中。当前服务尚未提供自动恢复状态，如长时间无进度，可手动刷新查看。
          </div>
          <div v-if="task.status === 'pending'" class="hint-block">
            任务等待执行中，可手动刷新查看进度。
          </div>
        </div>
      </div>

      <!-- 参数 -->
      <div class="card" style="margin-top: 16px;">
        <div class="card-header">任务参数</div>
        <div class="card-body">
          <el-descriptions :column="2" border>
            <el-descriptions-item label="目标题库">{{ bankLabel }}</el-descriptions-item>
            <el-descriptions-item label="知识点">{{ knowledgeLabel }}</el-descriptions-item>
            <el-descriptions-item label="题型">{{ typeLabel }}</el-descriptions-item>
            <el-descriptions-item label="难度">{{ difficultyLabel }}</el-descriptions-item>
            <el-descriptions-item label="创建时间">{{ formatDateTime(task.created_at) }}</el-descriptions-item>
            <el-descriptions-item label="开始时间">{{ formatDateTime(task.started_at) }}</el-descriptions-item>
            <el-descriptions-item label="完成时间">{{ formatDateTime(task.completed_at) }}</el-descriptions-item>
            <el-descriptions-item label="发起管理员ID">{{ task.created_by }}</el-descriptions-item>
          </el-descriptions>
        </div>
      </div>

      <!-- 错误摘要 -->
      <div v-if="task.error_summary" class="card error-card" style="margin-top: 16px;">
        <div class="card-header error-header">
          <AlertTriangle :size="16" style="margin-right: 6px;" />
          错误摘要
        </div>
        <div class="card-body">
          <pre class="error-text">{{ task.error_summary }}</pre>
        </div>
      </div>

      <!-- 关联题目 -->
      <div class="card" style="margin-top: 16px;">
        <div class="card-header">
          关联生成题目（{{ task.questions.length }}）
          <el-button text type="primary" size="small" style="margin-left: 12px;" @click="goToList">
            <ExternalLink :size="14" style="margin-right: 4px;" />
            进入题目审核
          </el-button>
        </div>
        <div class="card-body">
          <div v-if="task.questions.length === 0" class="empty-hint">
            暂无关联题目
          </div>
          <el-table v-else :data="task.questions" style="width: 100%;">
            <el-table-column prop="id" label="题目ID" width="80" align="center" />
            <el-table-column prop="content" label="题目摘要" min-width="260" show-overflow-tooltip />
            <el-table-column label="题型" width="100" align="center">
              <template #default="{ row }">
                {{ QUESTION_TYPE_LABELS[row.question_type] || row.question_type }}
              </template>
            </el-table-column>
            <el-table-column label="难度" width="80" align="center">
              <template #default="{ row }">
                {{ DIFFICULTY_LABELS[row.difficulty] || row.difficulty }}
              </template>
            </el-table-column>
            <el-table-column label="状态" width="100" align="center">
              <template #default="{ row }">
                <QuestionStatusTag :status="row.status" />
              </template>
            </el-table-column>
            <el-table-column prop="option_count" label="选项数" width="80" align="center" />
            <el-table-column label="操作" width="130" align="center">
              <template #default="{ row }">
                <el-button text type="primary" size="small" @click="goToReview(row.id)">
                  查看并审核
                </el-button>
              </template>
            </el-table-column>
          </el-table>
          <div class="hint-block" style="margin-top: 12px;">
            任务成功不代表题目已发布：生成的题目状态为「{{ QUESTION_STATUS_LABELS['pending_review'] }}」，需逐道审核通过后才可组卷。
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.header-actions {
  display: flex;
  gap: 8px;
}

.status-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.status-text {
  font-size: 14px;
  color: var(--color-muted-foreground);
}

.progress-block {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.progress-label {
  display: flex;
  justify-content: space-between;
  font-size: 14px;
  color: var(--color-muted-foreground);
}

.progress-value {
  font-weight: 600;
  color: var(--color-foreground);
}

.counts-row {
  display: flex;
  gap: 20px;
  font-size: 13px;
  color: var(--color-muted-foreground);
  margin-top: 4px;
}

.counts-row .ok b { color: var(--color-success, #059669); }
.counts-row .dup b { color: var(--color-warning, #D97706); }
.counts-row .fail b { color: var(--color-error, #DC2626); }

.hint-block {
  margin-top: 12px;
  padding: 10px 12px;
  background: var(--color-muted);
  border-radius: var(--radius-md);
  font-size: 13px;
  color: var(--color-muted-foreground);
}

.error-header {
  color: var(--color-error, #DC2626);
  display: flex;
  align-items: center;
}

.error-text {
  margin: 0;
  font-family: inherit;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 13px;
  color: var(--color-error, #DC2626);
}

.empty-hint {
  font-size: 13px;
  color: var(--color-muted-foreground);
  padding: 16px 0;
}
</style>
