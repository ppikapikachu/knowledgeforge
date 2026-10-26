<script setup lang="ts">
/**
 * AI 审核批次详情
 * GET /api/v1/question-reviews/batches/{batch_id}
 * queued/running 时每 3 秒轮询；终态停止；路由离开清理。
 */
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getQuestionReviewBatchDetail } from '@/api/questionReview'
import type { ReviewBatchDetail, ReviewBatchItem } from '@/types/questionReviewBatch'
import {
  getBatchStatusLabel,
  getBatchStatusClass,
  getBatchItemStatusLabel,
  getBatchItemStatusClass,
  getSkipReasonLabel,
  isBatchRunning,
} from '@/constants/questionReviewBatch'
import {
  getAiDecisionLabel,
  getAiDecisionClass,
  getRiskLevelLabel,
  getRiskLevelClass,
  getIssueTypeLabel,
} from '@/constants/questionReview'
import { QUESTION_TYPE_LABELS, formatDateTime } from '@/constants/questionManagement'
import { ElMessage } from 'element-plus'
import {
  ArrowLeft,
  RefreshCw,
  ClipboardList,
  CheckCircle,
  XCircle,
  AlertTriangle,
  ExternalLink,
  Eye,
} from 'lucide-vue-next'

const route = useRoute()
const router = useRouter()

const loading = ref(true)
const batch = ref<ReviewBatchDetail | null>(null)
const loadError = ref(false)
const refreshFailed = ref(false)

const batchId = computed(() => Number(route.params.batchId))
let pollTimer: ReturnType<typeof setInterval> | null = null
let polling = false

async function fetchData() {
  if (polling) return
  polling = true
  try {
    const res = await getQuestionReviewBatchDetail(batchId.value)
    batch.value = res.data
    refreshFailed.value = false
    loadError.value = false
    if (!isBatchRunning(res.data.status)) {
      stopPolling()
    }
  } catch {
    refreshFailed.value = true
    if (!batch.value) loadError.value = true
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

function getStatusIcon(status: string) {
  if (status === 'completed') return CheckCircle
  if (status === 'failed') return XCircle
  if (status === 'partial') return AlertTriangle
  return ClipboardList
}

function itemStatusIcon(status: string) {
  if (status === 'completed') return CheckCircle
  if (status === 'failed') return XCircle
  if (status === 'skipped') return AlertTriangle
  return ClipboardList
}

function goToQuestion(qId: number) {
  router.push(`/question-management/questions/${qId}`)
}

function goToRecords(item: ReviewBatchItem) {
  router.push(
    `/question-management/ai-reviews?question_id=${item.question_id}&batch_id=${batchId.value}&trigger_source=manual_batch`,
  )
}

function goToReviewQueue() {
  router.push('/question-management/review')
}

onMounted(async () => {
  await fetchData()
  if (batch.value && isBatchRunning(batch.value.status)) {
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
        <h2>AI 审核批次详情</h2>
        <p class="description">批次 #{{ batchId }}</p>
      </div>
      <div class="header-actions">
        <el-button @click="fetchData">
          <RefreshCw :size="16" style="margin-right: 4px;" />
          刷新
        </el-button>
        <el-button @click="router.push('/question-management/review-batches')">
          <ClipboardList :size="16" style="margin-right: 4px;" />
          批次列表
        </el-button>
      </div>
    </div>

    <!-- 刷新失败提示（保留已加载数据） -->
    <div v-if="refreshFailed && batch" class="card" style="margin-bottom: 12px;">
      <div class="card-body" style="padding: 12px 16px;">
        <div class="refresh-warning">
          <AlertTriangle :size="16" />
          <span>刷新失败，显示的是最后一次成功加载的数据。</span>
          <el-button size="small" @click="fetchData">重试</el-button>
        </div>
      </div>
    </div>

    <!-- 错误 -->
    <div v-if="loadError && !batch" class="card">
      <div class="empty-state">
        <p class="title">批次加载失败</p>
        <p class="description">批次不存在或无法获取数据，请检查后端服务</p>
        <el-button type="primary" @click="fetchData">重新加载</el-button>
        <el-button @click="router.push('/question-management/review-batches')">返回批次列表</el-button>
      </div>
    </div>

    <!-- Loading -->
    <div v-else-if="loading && !batch" class="card">
      <div class="card-body">
        <el-skeleton :rows="8" animated />
      </div>
    </div>

    <template v-if="batch">
      <!-- 总体信息 -->
      <div class="card">
        <div class="card-header">
          批次概览
          <span :class="['status-badge', `status-badge--${getBatchStatusClass(batch.status)}`]" style="margin-left: 12px;">
            {{ getBatchStatusLabel(batch.status) }}
          </span>
        </div>
        <div class="card-body">
          <div class="batch-meta">
            <div class="meta-item">批次 ID：<strong>#{{ batch.id }}</strong></div>
            <div class="meta-item">创建人：管理员 #{{ batch.created_by }}</div>
            <div class="meta-item">创建时间：{{ formatDateTime(batch.created_at) }}</div>
            <div class="meta-item">开始时间：{{ formatDateTime(batch.started_at) }}</div>
            <div class="meta-item">完成时间：{{ formatDateTime(batch.finished_at) }}</div>
          </div>

          <!-- 进度 -->
          <div class="progress-block">
            <div class="progress-label">
              <span>审核进度：已处理 {{ batch.progress.processed }} / 接受 {{ batch.progress.accepted }}</span>
              <span>待处理 {{ batch.progress.pending }}</span>
            </div>
            <el-progress
              :percentage="batch.progress.accepted > 0 ? Math.round((batch.progress.processed / batch.progress.accepted) * 100) : 0"
              :stroke-width="12"
              :status="batch.status === 'failed' ? 'exception' : (batch.status === 'completed' ? 'success' : undefined)"
            />
            <div class="counts-row">
              <span>请求 <b>{{ batch.total_count }}</b></span>
              <span>接受 <b>{{ batch.accepted_count }}</b></span>
              <span class="ok">通过 <b>{{ batch.auto_approved_count }}</b></span>
              <span class="err">驳回 <b>{{ batch.auto_rejected_count }}</b></span>
              <span class="warn">转人工 <b>{{ batch.manual_review_count }}</b></span>
              <span class="err">失败 <b>{{ batch.failed_count }}</b></span>
              <span>跳过 <b>{{ batch.skipped_count }}</b></span>
              <span>待处理 <b>{{ batch.pending_count }}</b></span>
            </div>
          </div>

          <div v-if="batch.error_message" class="error-block">
            <div class="error-title">错误信息</div>
            <div class="error-msg">{{ batch.error_message }}</div>
          </div>
        </div>
      </div>

      <!-- 逐题明细 -->
      <div class="card" style="margin-top: 16px;">
        <div class="card-header">逐题结果（{{ batch.items.length }}）</div>
        <div class="card-body">
          <el-table :data="batch.items" style="width: 100%;">
            <el-table-column prop="question_id" label="题目ID" width="80" align="center">
              <template #default="{ row }">
                <el-link type="primary" @click="goToQuestion(row.question_id)">
                  #{{ row.question_id }}
                </el-link>
              </template>
            </el-table-column>
            <el-table-column prop="question_content" label="题干摘要" min-width="180" show-overflow-tooltip>
              <template #default="{ row }">{{ row.question_content || '-' }}</template>
            </el-table-column>
            <el-table-column label="题型" width="90" align="center">
              <template #default="{ row }">
                {{ QUESTION_TYPE_LABELS[row.question_type || ''] || row.question_type || '-' }}
              </template>
            </el-table-column>
            <el-table-column label="item 状态" width="100" align="center">
              <template #default="{ row }">
                <span :class="['status-badge', `status-badge--${getBatchItemStatusClass(row.status)}`]">
                  {{ getBatchItemStatusLabel(row.status) }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="审核结论" width="110" align="center">
              <template #default="{ row }">
                <span v-if="row.review_decision" :class="['status-badge', `status-badge--${getAiDecisionClass(row.review_decision)}`]">
                  {{ getAiDecisionLabel(row.review_decision) }}
                </span>
                <span v-else class="muted-text">{{ row.status === 'skipped' ? '无审核结论' : '-' }}</span>
              </template>
            </el-table-column>
            <el-table-column label="风险" width="80" align="center">
              <template #default="{ row }">
                <span v-if="row.review_risk_level" :class="['status-badge', `status-badge--${getRiskLevelClass(row.review_risk_level)}`]">
                  {{ getRiskLevelLabel(row.review_risk_level) }}
                </span>
                <span v-else class="muted-text">-</span>
              </template>
            </el-table-column>
            <el-table-column label="跳过/失败原因" min-width="150" show-overflow-tooltip>
              <template #default="{ row }">
                <template v-if="row.status === 'skipped'">
                  <div>{{ row.skip_reason_text || getSkipReasonLabel(row.skip_reason) }}</div>
                  <div v-if="row.skip_reason" class="muted-text">原因码：{{ row.skip_reason }}</div>
                </template>
                <template v-else-if="row.status === 'failed'">
                  <div class="error-msg">{{ row.error_message || row.error_code || '未知错误' }}</div>
                </template>
                <span v-else class="muted-text">-</span>
              </template>
            </el-table-column>
            <el-table-column label="问题类型" min-width="120" show-overflow-tooltip>
              <template #default="{ row }">
                <template v-if="row.review_issue_types && row.review_issue_types.length > 0">
                  <span v-for="(issue, idx) in row.review_issue_types" :key="idx" class="issue-tag">
                    {{ getIssueTypeLabel(issue) }}
                  </span>
                </template>
                <span v-else class="muted-text">-</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="110" align="center" fixed="right">
              <template #default="{ row }">
                <el-button
                  v-if="row.review_record_id"
                  text
                  type="primary"
                  size="small"
                  @click="goToRecords(row)"
                >
                  <Eye :size="14" style="margin-right: 4px;" />
                  审核详情
                </el-button>
                <span v-else class="muted-text">-</span>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </div>

      <!-- 后续操作提示 -->
      <div class="card" style="margin-top: 16px;">
        <div class="card-body" style="padding: 12px 16px;">
          <div class="hint-block">
            提示：批次不支持取消或自动重试。如需重新审核失败或跳过的题目，请返回
            <el-link type="primary" @click="goToReviewQueue">题目审核</el-link>
            重新选择仍处于待审核状态的题目，创建新批次。
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

.refresh-warning {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  background: #FFFBEB;
  border: 1px solid #FCD34D;
  border-radius: var(--radius-md);
  font-size: 13px;
  color: #92400E;
}

.batch-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  font-size: 13px;
  color: var(--color-muted-foreground);
  margin-bottom: 16px;
}

.progress-block {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.progress-label {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  color: var(--color-muted-foreground);
}

.counts-row {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  font-size: 13px;
  color: var(--color-muted-foreground);
}

.counts-row .ok b { color: var(--color-success, #059669); }
.counts-row .err b { color: var(--color-error, #DC2626); }
.counts-row .warn b { color: var(--color-warning, #D97706); }

.error-block {
  margin-top: 12px;
  padding: 12px;
  background: #FEF2F2;
  border-radius: var(--radius-md);
}

.error-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-error, #DC2626);
  margin-bottom: 4px;
}

.error-msg {
  font-size: 12px;
  color: var(--color-error, #DC2626);
}

.muted-text {
  color: var(--color-muted-foreground);
  font-size: 12px;
}

.issue-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  background: var(--color-muted);
  color: var(--color-foreground);
  margin: 2px;
}

.hint-block {
  font-size: 13px;
  color: var(--color-muted-foreground);
  line-height: 1.6;
}
</style>
