<script setup lang="ts">
/**
 * AI 质量审核记录页面
 * GET /api/v1/question-reviews/records
 * query: task_id, question_id, decision, execution_status, page, page_size
 */
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { getReviewRecords } from '@/api/questionReview'
import type { QuestionReviewRecord, QuestionReviewRecordQueryParams, AiReviewDecision, AiReviewExecutionStatus } from '@/types/questionReview'
import {
  getAiDecisionLabel,
  getAiDecisionClass,
  getRiskLevelLabel,
  getRiskLevelClass,
  getExecutionStatusLabel,
  getExecutionStatusClass,
  getIssueTypeLabel,
} from '@/constants/questionReview'
import { QUESTION_TYPE_LABELS } from '@/constants/questionManagement'
import DedupStatusCard from '@/components/question-management/DedupStatusCard.vue'
import { ElMessage } from 'element-plus'
import { Search, RefreshCw, Shield, Eye, ArrowRight, ClipboardList } from 'lucide-vue-next'

const router = useRouter()
const route = useRoute()

const loading = ref(true)
const tableData = ref<QuestionReviewRecord[]>([])
const total = ref(0)
const loadError = ref(false)

const queryParams = ref<QuestionReviewRecordQueryParams>({
  page: 1,
  page_size: 20,
  task_id: undefined,
  question_id: undefined,
  decision: undefined,
  execution_status: undefined,
})

// 详情弹窗
const detailVisible = ref(false)
const detailRecord = ref<QuestionReviewRecord | null>(null)

const hasFilters = computed(() =>
  !!(
    queryParams.value.task_id ||
    queryParams.value.question_id ||
    queryParams.value.decision ||
    queryParams.value.execution_status
  ),
)

async function fetchData() {
  loading.value = true
  loadError.value = false
  try {
    const params: QuestionReviewRecordQueryParams = { ...queryParams.value }
    if (!params.task_id) delete params.task_id
    if (!params.question_id) delete params.question_id
    if (!params.decision) delete params.decision
    if (!params.execution_status) delete params.execution_status

    const res = await getReviewRecords(params)
    tableData.value = res.data.items
    total.value = res.data.total
  } catch {
    loadError.value = true
    tableData.value = []
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  queryParams.value.page = 1
  fetchData()
}

function handleReset() {
  queryParams.value = {
    page: 1,
    page_size: 20,
    task_id: undefined,
    question_id: undefined,
    decision: undefined,
    execution_status: undefined,
  }
  fetchData()
}

function handleFilterChange() {
  queryParams.value.page = 1
  fetchData()
}

function handlePageChange(page: number) {
  queryParams.value.page = page
  fetchData()
}

function handleSizeChange(size: number) {
  queryParams.value.page_size = size
  queryParams.value.page = 1
  fetchData()
}

function openDetail(record: QuestionReviewRecord) {
  detailRecord.value = record
  detailVisible.value = true
}

function goToQuestion(id: number) {
  router.push(`/question-management/questions/${id}`)
}

function goToTask(taskId: number) {
  router.push(`/question-management/tasks/${taskId}`)
}

onMounted(() => {
  // 从 URL 读取过滤参数（从任务列表跳转时带入）
  const taskParam = route.query.task_id
  const questionParam = route.query.question_id
  const decisionParam = route.query.decision
  const execParam = route.query.execution_status

  if (taskParam) queryParams.value.task_id = Number(taskParam)
  if (questionParam) queryParams.value.question_id = Number(questionParam)
  if (decisionParam) queryParams.value.decision = decisionParam as AiReviewDecision
  if (execParam) queryParams.value.execution_status = execParam as AiReviewExecutionStatus

  fetchData()
})
</script>

<template>
  <div class="page-container">
    <div class="page-header">
      <div>
        <h2>AI 审核记录</h2>
        <p class="description">查看 AI 质量审核的执行结果、依据和风险评估</p>
      </div>
    </div>

    <!-- 筛选 -->
    <div class="filter-toolbar">
      <el-input
        v-model="queryParams.task_id"
        placeholder="任务 ID"
        clearable
        style="width: 110px;"
        type="number"
        @change="handleFilterChange"
      />
      <el-input
        v-model="queryParams.question_id"
        placeholder="题目 ID"
        clearable
        style="width: 110px;"
        type="number"
        @change="handleFilterChange"
      />
      <el-select
        v-model="queryParams.decision"
        placeholder="审核结论"
        clearable
        style="width: 140px;"
        @change="handleFilterChange"
      >
        <el-option label="AI 自动通过" value="auto_approve" />
        <el-option label="AI 自动驳回" value="auto_reject" />
        <el-option label="建议人工审核" value="manual_review" />
      </el-select>
      <el-select
        v-model="queryParams.execution_status"
        placeholder="执行状态"
        clearable
        style="width: 130px;"
        @change="handleFilterChange"
      >
        <el-option label="执行成功" value="success" />
        <el-option label="执行失败" value="failed" />
        <el-option label="已跳过" value="skipped" />
      </el-select>

      <el-button type="primary" @click="handleSearch">
        <Search :size="16" style="margin-right: 4px;" />
        搜索
      </el-button>
      <el-button @click="handleReset">
        <RefreshCw :size="16" style="margin-right: 4px;" />
        重置
      </el-button>
    </div>

    <!-- 错误 -->
    <div v-if="loadError" class="card">
      <div class="empty-state">
        <p class="title">加载失败</p>
        <p class="description">无法获取审核记录，请检查后端服务后重试</p>
        <el-button type="primary" @click="fetchData">重新加载</el-button>
      </div>
    </div>

    <!-- Loading -->
    <div v-else-if="loading" class="card">
      <div class="card-body">
        <el-skeleton :rows="8" animated />
      </div>
    </div>

    <!-- 空 -->
    <div v-else-if="tableData.length === 0" class="card">
      <div class="empty-state">
        <Shield :size="48" />
        <p class="title">{{ hasFilters ? '筛选条件下暂无记录' : '暂无 AI 审核记录' }}</p>
        <p class="description">
          {{ hasFilters ? '请调整筛选条件后重试' : '启用 AI 自动审核的生成任务完成后，记录会自动出现在这里' }}
        </p>
      </div>
    </div>

    <!-- 表格 -->
    <div v-else class="card">
      <el-table :data="tableData" style="width: 100%;">
        <el-table-column prop="id" label="记录ID" width="80" align="center" />
        <el-table-column prop="question_id" label="题目" width="80" align="center">
          <template #default="{ row }">
            <el-link type="primary" @click.stop="goToQuestion(row.question_id)">
              #{{ row.question_id }}
            </el-link>
          </template>
        </el-table-column>
        <el-table-column label="审核结论" width="130" align="center">
          <template #default="{ row }">
            <span :class="['status-badge', `status-badge--${getAiDecisionClass(row.decision)}`]">
              {{ getAiDecisionLabel(row.decision) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="风险级别" width="90" align="center">
          <template #default="{ row }">
            <span :class="['status-badge', `status-badge--${getRiskLevelClass(row.risk_level)}`]">
              {{ getRiskLevelLabel(row.risk_level) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="执行状态" width="100" align="center">
          <template #default="{ row }">
            <span :class="['status-badge', `status-badge--${getExecutionStatusClass(row.execution_status)}`]">
              {{ getExecutionStatusLabel(row.execution_status) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="问题类型" min-width="150" show-overflow-tooltip>
          <template #default="{ row }">
            <template v-if="row.issue_types && row.issue_types.length > 0">
              <span v-for="(issue, idx) in row.issue_types" :key="idx" class="issue-tag">
                {{ getIssueTypeLabel(issue) }}
              </span>
            </template>
            <span v-else class="muted-text">-</span>
          </template>
        </el-table-column>
        <el-table-column label="耗时" width="80" align="center">
          <template #default="{ row }">
            {{ row.duration_ms !== null ? `${row.duration_ms}ms` : '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="question_type" label="题型" width="95" align="center">
          <template #default="{ row }">
            {{ QUESTION_TYPE_LABELS[row.question_type || ''] || row.question_type || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="题库" width="110" align="center">
          <template #default="{ row }">
            {{ row.question_bank_name || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="generation_task_id" label="任务" width="80" align="center">
          <template #default="{ row }">
            <el-link v-if="row.generation_task_id" type="primary" @click.stop="goToTask(row.generation_task_id)">
              #{{ row.generation_task_id }}
            </el-link>
            <span v-else class="muted-text">-</span>
          </template>
        </el-table-column>
        <el-table-column label="审核时间" width="150" align="center">
          <template #default="{ row }">
            {{ row.created_at ? new Date(row.created_at).toLocaleString('zh-CN') : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right" align="center">
          <template #default="{ row }">
            <el-button text type="primary" size="small" @click="openDetail(row)">
              <Eye :size="14" style="margin-right: 4px;" />
              详情
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="queryParams.page"
          v-model:page-size="queryParams.page_size"
          :total="total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          @current-change="handlePageChange"
          @size-change="handleSizeChange"
        />
      </div>
    </div>

    <!-- 详情弹窗 -->
    <el-dialog
      v-model="detailVisible"
      title="AI 审核记录详情"
      width="800px"
      :close-on-click-modal="false"
    >
      <div v-if="detailRecord" class="detail-container">
        <!-- 基本结论 -->
        <div class="detail-section">
          <div class="info-grid">
            <div class="info-item">
              <span class="info-label">审核结论</span>
              <span :class="['status-badge', `status-badge--${getAiDecisionClass(detailRecord.decision)}`]">
                {{ getAiDecisionLabel(detailRecord.decision) }}
              </span>
            </div>
            <div class="info-item">
              <span class="info-label">风险级别</span>
              <span :class="['status-badge', `status-badge--${getRiskLevelClass(detailRecord.risk_level)}`]">
                {{ getRiskLevelLabel(detailRecord.risk_level) }}
              </span>
            </div>
            <div class="info-item">
              <span class="info-label">执行状态</span>
              <span :class="['status-badge', `status-badge--${getExecutionStatusClass(detailRecord.execution_status)}`]">
                {{ getExecutionStatusLabel(detailRecord.execution_status) }}
              </span>
            </div>
          </div>
        </div>

        <!-- 审核理由 -->
        <div v-if="detailRecord.reason" class="detail-section">
          <div class="section-title">审核理由</div>
          <pre class="reason-text">{{ detailRecord.reason }}</pre>
        </div>

        <!-- 问题类型 -->
        <div v-if="detailRecord.issue_types && detailRecord.issue_types.length > 0" class="detail-section">
          <div class="section-title">问题类型</div>
          <div class="issue-tags">
            <span v-for="(issue, idx) in detailRecord.issue_types" :key="idx" class="issue-tag">
              {{ getIssueTypeLabel(issue) }}
            </span>
          </div>
        </div>

        <!-- 检查项 -->
        <div v-if="detailRecord.checks && Object.keys(detailRecord.checks).length > 0" class="detail-section">
          <div class="section-title">检查项</div>
          <div class="checks-grid">
            <div v-for="(val, key) in detailRecord.checks" :key="key" class="check-item">
              <span class="check-key">{{ key }}</span>
              <span :class="['status-badge', `status-badge--${val === 'pass' ? 'success' : val === 'fail' ? 'error' : val === 'uncertain' ? 'warning' : 'muted'}`]">
                {{ val === 'pass' ? '通过' : val === 'fail' ? '不通过' : val === 'uncertain' ? '不确定' : val === 'not_applicable' ? '不适用' : val }}
              </span>
            </div>
          </div>
        </div>

        <!-- 证据 -->
        <div v-if="detailRecord.evidence && detailRecord.evidence.length > 0" class="detail-section">
          <div class="section-title">审核证据</div>
          <div v-for="(ev, idx) in detailRecord.evidence" :key="idx" class="evidence-item">
            <div class="evidence-meta">
              <span>知识点 #{{ ev.knowledge_id }}</span>
            </div>
            <div class="evidence-excerpt">
              <div class="evidence-label">资料原文摘录：</div>
              <pre class="evidence-text">{{ ev.source_excerpt }}</pre>
            </div>
            <div class="evidence-explanation">
              <div class="evidence-label">说明：</div>
              <pre class="evidence-text">{{ ev.explanation }}</pre>
            </div>
          </div>
        </div>

        <!-- 模型信息 -->
        <div class="detail-section">
          <div class="info-grid">
            <div class="info-item">
              <span class="info-label">模型名</span>
              <span>{{ detailRecord.model_name || '-' }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">Prompt 版本</span>
              <span>{{ detailRecord.prompt_version || '-' }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">审核耗时</span>
              <span>{{ detailRecord.duration_ms !== null ? `${detailRecord.duration_ms}ms` : '-' }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">内容哈希</span>
              <span class="hash-text">{{ detailRecord.reviewed_content_hash || '-' }}</span>
            </div>
          </div>
        </div>

        <!-- 错误信息 -->
        <div v-if="detailRecord.error_code || detailRecord.error_message" class="detail-section">
          <div class="section-title error-title">错误信息</div>
          <div class="error-info">
            <div v-if="detailRecord.error_code">错误码：{{ detailRecord.error_code }}</div>
            <pre v-if="detailRecord.error_message" class="error-text">{{ detailRecord.error_message }}</pre>
          </div>
        </div>

        <!-- reopen 信息 -->
        <div v-if="detailRecord.reopened_by" class="detail-section">
          <div class="section-title">已重新开启人工审核</div>
          <div class="reopen-info">
            <div>操作人：管理员 #{{ detailRecord.reopened_by }}</div>
            <div>操作时间：{{ detailRecord.reopened_at ? new Date(detailRecord.reopened_at).toLocaleString('zh-CN') : '-' }}</div>
            <div>原因：{{ detailRecord.reopen_reason }}</div>
          </div>
        </div>

        <!-- 记录元信息 -->
        <div class="detail-section">
          <div class="info-grid">
            <div class="info-item">
              <span class="info-label">审核轮次</span>
              <span>{{ detailRecord.review_round }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">触发来源</span>
              <span>{{ detailRecord.trigger_source }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">题目状态</span>
              <span>{{ detailRecord.question_status || '-' }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">审核时间</span>
              <span>{{ detailRecord.created_at ? new Date(detailRecord.created_at).toLocaleString('zh-CN') : '-' }}</span>
            </div>
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<style scoped>
.filter-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.muted-text {
  color: var(--color-muted-foreground);
  font-size: 12px;
}

.issue-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  background: var(--color-muted);
  color: var(--color-foreground);
  margin: 2px;
}

.detail-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.detail-section {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 16px;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-foreground);
  margin-bottom: 8px;
}

.error-title {
  color: var(--color-error, #DC2626);
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.info-label {
  font-size: 11px;
  color: var(--color-muted-foreground);
}

.reason-text {
  margin: 0;
  font-family: inherit;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 13px;
  line-height: 1.6;
  color: var(--color-foreground);
  background: var(--color-muted);
  padding: 10px;
  border-radius: var(--radius-md);
}

.issue-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.checks-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
}

.check-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 10px;
  background: var(--color-muted);
  border-radius: var(--radius-sm);
}

.check-key {
  font-size: 12px;
  color: var(--color-foreground);
}

.evidence-item {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 12px;
  margin-bottom: 8px;
}

.evidence-meta {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-foreground);
  margin-bottom: 8px;
}

.evidence-label {
  font-size: 12px;
  color: var(--color-muted-foreground);
  margin-bottom: 4px;
}

.evidence-text {
  margin: 0;
  font-family: inherit;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 12px;
  line-height: 1.5;
  color: var(--color-foreground);
  background: var(--color-muted);
  padding: 8px;
  border-radius: var(--radius-sm);
}

.evidence-explanation {
  margin-top: 8px;
}

.hash-text {
  font-family: monospace;
  font-size: 11px;
  word-break: break-all;
  color: var(--color-muted-foreground);
}

.error-info {
  font-size: 13px;
  color: var(--color-error, #DC2626);
}

.error-text {
  margin: 4px 0 0 0;
  font-family: inherit;
  white-space: pre-wrap;
  font-size: 12px;
  line-height: 1.5;
}

.reopen-info {
  font-size: 13px;
  color: var(--color-foreground);
  line-height: 1.8;
}
</style>
