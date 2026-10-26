<script setup lang="ts">
/**
 * 题目审核（待审核列表 + AI 批量审核）
 * GET /api/v1/questions?status=pending_review&...
 * POST /api/v1/question-reviews/batches/preview
 * POST /api/v1/question-reviews/batches
 */
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { getQuestionList } from '@/api/question'
import { previewQuestionReviewBatch, createQuestionReviewBatch } from '@/api/questionReview'
import { useQuestionLookups } from '@/composables/useQuestionLookups'
import type { Question, QuestionQueryParams } from '@/types/question'
import type {
  ReviewBatchPreviewResponse,
  ReviewBatchPreviewItem,
  ReviewBatchCreateResponse,
} from '@/types/questionReviewBatch'
import {
  QUESTION_TYPES,
  DIFFICULTIES,
  QUESTION_TYPE_LABELS,
  DIFFICULTY_LABELS,
  DIFFICULTY_CLASSES,
  truncateText,
} from '@/constants/questionManagement'
import { getSkipReasonLabel } from '@/constants/questionReviewBatch'
import QuestionStatusTag from '@/components/question-management/QuestionStatusTag.vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, RefreshCw, Inbox, Eye, Sparkles, CheckCircle, XCircle } from 'lucide-vue-next'

const router = useRouter()
const { banks, loadAll, bankName, knowledgeName, searchKnowledge, knowledgeLoading } = useQuestionLookups()

const loading = ref(true)
const tableData = ref<Question[]>([])
const total = ref(0)
const loadError = ref(false)

const knowledgeOptions = ref<{ id: number; name: string }[]>([])

// 多选
const selectedIds = ref<number[]>([])
const selectedRows = ref<Question[]>([])

// 预检弹窗
const previewVisible = ref(false)
const previewLoading = ref(false)
const previewData = ref<ReviewBatchPreviewResponse | null>(null)
const creating = ref(false)
const createResult = ref<ReviewBatchCreateResponse | null>(null)

const queryParams = ref<QuestionQueryParams>({
  page: 1,
  page_size: 20,
  status: 'pending_review',
  keyword: '',
  question_type: undefined,
  difficulty: undefined,
  question_bank_id: undefined,
  knowledge_id: undefined,
})

// 关键词防抖
let debounceTimer: ReturnType<typeof setTimeout> | null = null
function handleKeywordInput() {
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    queryParams.value.page = 1
    fetchData()
  }, 400)
}
onUnmounted(() => {
  if (debounceTimer) clearTimeout(debounceTimer)
})

const hasFilters = computed(() =>
  !!(
    queryParams.value.keyword ||
    queryParams.value.question_type ||
    queryParams.value.difficulty ||
    queryParams.value.question_bank_id ||
    queryParams.value.knowledge_id
  ),
)

const selectedCount = computed(() => selectedIds.value.length)

async function fetchData() {
  loading.value = true
  loadError.value = false
  try {
    const params: QuestionQueryParams = {
      page: queryParams.value.page,
      page_size: queryParams.value.page_size,
      status: 'pending_review',
    }
    if (queryParams.value.keyword) params.keyword = queryParams.value.keyword
    if (queryParams.value.question_type) params.question_type = queryParams.value.question_type
    if (queryParams.value.difficulty) params.difficulty = queryParams.value.difficulty
    if (queryParams.value.question_bank_id) params.question_bank_id = queryParams.value.question_bank_id
    if (queryParams.value.knowledge_id) params.knowledge_id = queryParams.value.knowledge_id

    const res = await getQuestionList(params)
    tableData.value = res.data.items
    total.value = res.data.total
    // 翻页后清理跨页选择（当前页选择模式）
    selectedIds.value = []
    selectedRows.value = []
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
    status: 'pending_review',
    keyword: '',
    question_type: undefined,
    difficulty: undefined,
    question_bank_id: undefined,
    knowledge_id: undefined,
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

// 多选处理
function handleSelectionChange(rows: Question[]) {
  selectedRows.value = rows
  selectedIds.value = [...new Set(rows.map((r) => r.id))]
}

async function handleKnowledgeSearch(keyword: string) {
  knowledgeLoading.value = true
  try {
    const items = await searchKnowledge(keyword)
    knowledgeOptions.value = items.map((k) => ({ id: k.id, name: k.name }))
  } catch {
    ElMessage.error('知识点搜索失败')
  } finally {
    knowledgeLoading.value = false
  }
}

function knowledgeLabelOf(q: Question): string {
  if (!q.knowledge_ids || q.knowledge_ids.length === 0) return '-'
  return q.knowledge_ids.map((id) => knowledgeName(id)).join('、')
}

function goToReview(qId: number) {
  router.push(`/question-management/questions/${qId}?from=review`)
}

// ---- AI 批量审核预检 ----
async function handleBatchReview() {
  if (selectedIds.value.length === 0) return

  previewData.value = null
  createResult.value = null
  previewVisible.value = true
  previewLoading.value = true
  try {
    const res = await previewQuestionReviewBatch({
      question_ids: [...selectedIds.value],
    })
    previewData.value = res.data
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '预检失败')
    previewVisible.value = false
  } finally {
    previewLoading.value = false
  }
}

// ---- 创建批次 ----
async function handleCreateBatch() {
  if (!previewData.value || previewData.value.eligible === 0) return

  creating.value = true
  try {
    // 提交原始 question_ids（不是仅 eligible），令服务端重新校验
    const res = await createQuestionReviewBatch({
      question_ids: [...selectedIds.value],
    })
    createResult.value = res.data
    ElMessage.success(`批次 #${res.data.batch_id} 已创建`)
    // 清理选择，刷新列表
    selectedIds.value = []
    selectedRows.value = []
    await fetchData()
  } catch (e) {
    const msg = e instanceof Error ? e.message : '创建批次失败'
    if (msg.includes('timeout') || msg.includes('超时')) {
      ElMessage.warning('请求结果暂不确定，请先到「AI 审核批次」列表核实，避免重复创建')
    } else {
      ElMessage.error(msg)
    }
  } finally {
    creating.value = false
  }
}

function closePreview() {
  previewVisible.value = false
  previewData.value = null
  createResult.value = null
}

function goToBatchDetail() {
  if (createResult.value) {
    router.push(`/question-management/review-batches/${createResult.value.batch_id}`)
    closePreview()
  }
}

function getPreviewItemById(id: number): ReviewBatchPreviewItem | undefined {
  return previewData.value?.items.find((i) => i.question_id === id)
}

onMounted(async () => {
  await Promise.all([loadAll(), fetchData(), handleKnowledgeSearch('')])
})
</script>

<template>
  <div class="page-container">
    <div class="page-header">
      <div>
        <h2>题目审核</h2>
        <p class="description">审核 AI 生成的待审核题目；支持多选后发起 AI 批量审核</p>
      </div>
      <el-button type="success" :disabled="selectedCount === 0" @click="handleBatchReview">
        <Sparkles :size="16" style="margin-right: 4px;" />
        AI 批量审核{{ selectedCount > 0 ? `（${selectedCount}）` : '' }}
      </el-button>
    </div>

    <!-- 筛选 -->
    <div class="filter-toolbar">
      <el-input
        v-model="queryParams.keyword"
        placeholder="搜索题目内容"
        clearable
        style="width: 200px;"
        @input="handleKeywordInput"
        @keyup.enter="handleSearch"
      >
        <template #prefix><Search :size="16" /></template>
      </el-input>

      <el-select
        v-model="queryParams.question_bank_id"
        placeholder="题库"
        clearable
        filterable
        style="width: 150px;"
        @change="handleFilterChange"
      >
        <el-option v-for="b in banks" :key="b.id" :label="b.name" :value="b.id" />
      </el-select>

      <el-select
        v-model="queryParams.knowledge_id"
        placeholder="知识点"
        clearable
        filterable
        remote
        :remote-method="handleKnowledgeSearch"
        :loading="knowledgeLoading"
        style="width: 160px;"
        @change="handleFilterChange"
      >
        <el-option v-for="k in knowledgeOptions" :key="k.id" :label="k.name" :value="k.id" />
      </el-select>

      <el-select
        v-model="queryParams.question_type"
        placeholder="题型"
        clearable
        style="width: 120px;"
        @change="handleFilterChange"
      >
        <el-option v-for="t in QUESTION_TYPES" :key="t.value" :label="t.label" :value="t.value" />
      </el-select>

      <el-select
        v-model="queryParams.difficulty"
        placeholder="难度"
        clearable
        style="width: 110px;"
        @change="handleFilterChange"
      >
        <el-option v-for="d in DIFFICULTIES" :key="d.value" :label="d.label" :value="d.value" />
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

    <!-- 选中提示 -->
    <div v-if="selectedCount > 0" class="selection-bar">
      已选 <strong>{{ selectedCount }}</strong> 道题目
      <span class="selection-hint">（仅限当前页选择）</span>
    </div>

    <!-- 错误 -->
    <div v-if="loadError" class="card">
      <div class="empty-state">
        <p class="title">加载失败</p>
        <p class="description">无法获取待审核题目，请检查后端服务后重试</p>
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
        <Inbox :size="48" />
        <p class="title">{{ hasFilters ? '筛选条件下暂无结果' : '暂无待审核题目' }}</p>
        <p class="description">
          {{ hasFilters ? '请调整筛选条件后重试' : 'AI 生成的题目会自动进入待审核队列' }}
        </p>
      </div>
    </div>

    <!-- 表格 -->
    <div v-else class="card">
      <el-table
        :data="tableData"
        style="width: 100%;"
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="50" align="center" />
        <el-table-column prop="id" label="ID" width="70" align="center" />
        <el-table-column label="题目摘要" min-width="280" show-overflow-tooltip>
          <template #default="{ row }">{{ truncateText(row.content, 60) }}</template>
        </el-table-column>
        <el-table-column label="题库" width="130" align="center">
          <template #default="{ row }">{{ bankName(row.question_bank_id) }}</template>
        </el-table-column>
        <el-table-column label="关联知识点" width="180" show-overflow-tooltip>
          <template #default="{ row }">{{ knowledgeLabelOf(row) }}</template>
        </el-table-column>
        <el-table-column label="题型" width="100" align="center">
          <template #default="{ row }">
            {{ QUESTION_TYPE_LABELS[row.question_type] || row.question_type }}
          </template>
        </el-table-column>
        <el-table-column label="难度" width="80" align="center">
          <template #default="{ row }">
            <span :class="['difficulty-badge', `difficulty-badge--${DIFFICULTY_CLASSES[row.difficulty] || ''}`]">
              {{ DIFFICULTY_LABELS[row.difficulty] || row.difficulty }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <QuestionStatusTag :status="row.status" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="110" fixed="right" align="center">
          <template #default="{ row }">
            <el-button text type="primary" size="small" @click="goToReview(row.id)">
              <Eye :size="14" style="margin-right: 4px;" />
              审核
            </el-button>
          </template>
        </el-table-column>
      </el-table>

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

    <!-- 预检弹窗 -->
    <el-dialog
      v-model="previewVisible"
      title="AI 批量审核预检"
      width="720px"
      :close-on-click-modal="false"
      @close="closePreview"
    >
      <!-- 创建成功 -->
      <div v-if="createResult" class="create-result">
        <div class="result-icon success">
          <CheckCircle :size="48" />
        </div>
        <div class="result-title">批次已创建</div>
        <div class="result-detail">
          <div>批次 ID：<strong>#{{ createResult.batch_id }}</strong></div>
          <div>已接受：<strong>{{ createResult.accepted }}</strong> 题</div>
          <div>跳过：<strong>{{ createResult.skipped }}</strong> 题</div>
        </div>
        <el-button type="primary" @click="goToBatchDetail">查看批次详情</el-button>
      </div>

      <!-- 预检内容 -->
      <template v-else>
        <!-- 加载中 -->
        <div v-if="previewLoading" class="preview-loading">
          <el-skeleton :rows="5" animated />
        </div>

        <template v-else-if="previewData">
          <!-- 统计 -->
          <div class="preview-stats">
            <div class="stat-item">
              <div class="stat-value">{{ previewData.requested }}</div>
              <div class="stat-label">请求数</div>
            </div>
            <div class="stat-item ok">
              <div class="stat-value">{{ previewData.eligible }}</div>
              <div class="stat-label">可审核</div>
            </div>
            <div class="stat-item warn">
              <div class="stat-value">{{ previewData.ineligible }}</div>
              <div class="stat-label">不可审核</div>
            </div>
          </div>

          <!-- 全部不可审核 -->
          <div v-if="previewData.eligible === 0" class="preview-warning">
            <XCircle :size="18" />
            <span>没有符合条件的题目可进行 AI 审核，请检查选择的题目。</span>
          </div>

          <!-- 说明 -->
          <div v-else class="preview-info">
            预检仅用于展示准入情况，创建后服务端会重新校验。不可审核的题目将被记录为 skipped。
          </div>

          <!-- 可审核清单 -->
          <div v-if="previewData.eligible > 0" class="preview-section">
            <div class="section-title">可审核题目（{{ previewData.eligible }}）</div>
            <div
              v-for="id in previewData.eligible_question_ids"
              :key="id"
              class="preview-item eligible"
            >
              <CheckCircle :size="16" class="icon-ok" />
              <span class="q-id">#{{ id }}</span>
              <span class="q-content">{{ getPreviewItemById(id)?.reason || '预检通过' }}</span>
            </div>
          </div>

          <!-- 不可审核清单 -->
          <div v-if="previewData.ineligible > 0" class="preview-section">
            <div class="section-title">不可审核题目（{{ previewData.ineligible }}）</div>
            <div
              v-for="item in previewData.items.filter(i => !i.eligible)"
              :key="item.question_id"
              class="preview-item ineligible"
            >
              <XCircle :size="16" class="icon-err" />
              <span class="q-id">#{{ item.question_id }}</span>
              <div class="q-reason">
                <div class="reason-text">{{ item.reason || getSkipReasonLabel(item.reason_code) }}</div>
                <div v-if="item.reason_code" class="reason-code">原因码：{{ item.reason_code }}</div>
              </div>
            </div>
          </div>
        </template>
      </template>

      <template #footer>
        <template v-if="!createResult">
          <el-button @click="closePreview">取消</el-button>
          <el-button
            v-if="previewData && previewData.eligible > 0"
            type="primary"
            :loading="creating"
            @click="handleCreateBatch"
          >
            确认创建批次（{{ previewData.eligible }} 题可审核）
          </el-button>
        </template>
        <el-button v-else @click="closePreview">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.selection-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  background: #EFF6FF;
  border: 1px solid #BFDBFE;
  border-radius: var(--radius-md);
  font-size: 13px;
  color: var(--color-foreground);
  margin-bottom: 12px;
}

.selection-hint {
  color: var(--color-muted-foreground);
  font-size: 12px;
}

.preview-loading {
  padding: 16px 0;
}

.preview-stats {
  display: flex;
  gap: 24px;
  padding: 16px;
  background: var(--color-muted);
  border-radius: var(--radius-md);
  margin-bottom: 16px;
}

.stat-item {
  text-align: center;
}

.stat-value {
  font-size: 24px;
  font-weight: 700;
  color: var(--color-foreground);
}

.stat-item.ok .stat-value { color: var(--color-success, #059669); }
.stat-item.warn .stat-value { color: var(--color-warning, #D97706); }

.stat-label {
  font-size: 12px;
  color: var(--color-muted-foreground);
  margin-top: 4px;
}

.preview-warning {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: #FEF2F2;
  border: 1px solid #FCA5A5;
  border-radius: var(--radius-md);
  color: var(--color-error, #DC2626);
  font-size: 13px;
  margin-bottom: 16px;
}

.preview-info {
  padding: 10px 14px;
  background: #FFFBEB;
  border-radius: var(--radius-md);
  font-size: 12px;
  color: #92400E;
  margin-bottom: 16px;
}

.preview-section {
  margin-bottom: 16px;
}

.section-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-muted-foreground);
  margin-bottom: 8px;
}

.preview-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px 12px;
  border-radius: var(--radius-md);
  margin-bottom: 4px;
  font-size: 13px;
}

.preview-item.eligible {
  background: #ECFDF5;
}

.preview-item.ineligible {
  background: #FEF2F2;
}

.icon-ok { color: var(--color-success, #059669); flex-shrink: 0; }
.icon-err { color: var(--color-error, #DC2626); flex-shrink: 0; }

.q-id {
  font-weight: 600;
  color: var(--color-foreground);
  min-width: 50px;
}

.q-content {
  color: var(--color-muted-foreground);
}

.q-reason {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.reason-text {
  color: var(--color-error, #DC2626);
}

.reason-code {
  font-size: 11px;
  color: var(--color-muted-foreground);
}

.create-result {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  padding: 24px;
}

.result-icon.success { color: var(--color-success, #059669); }

.result-title {
  font-size: 20px;
  font-weight: 600;
  color: var(--color-foreground);
}

.result-detail {
  text-align: center;
  font-size: 14px;
  line-height: 2;
}
</style>
