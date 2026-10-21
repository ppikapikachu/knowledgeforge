<script setup lang="ts">
/**
 * 去重疑点页面（含人工复核）
 * GET /api/v1/question-dedup/records
 * POST /api/v1/question-dedup/records/{id}/resolve
 */
import { ref, onMounted, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { getDedupRecords, resolveDedupRecord } from '@/api/questionDedup'
import type { DedupRecord, DedupRecordQueryParams, DedupDecision, ManualResolution } from '@/types/questionDedup'
import {
  getDecisionLabel,
  getDecisionClass,
  getMethodLabel,
  getScopeModeLabel,
  getManualResolutionLabel,
  getManualResolutionClass,
  formatScore,
} from '@/constants/questionDedup'
import { QUESTION_TYPE_LABELS } from '@/constants/questionManagement'
import DedupStatusCard from '@/components/question-management/DedupStatusCard.vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Search,
  RefreshCw,
  Eye,
  Shield,
  ArrowRight,
  Scale,
  UserCheck,
} from 'lucide-vue-next'

const router = useRouter()
const route = useRoute()

const loading = ref(true)
const tableData = ref<DedupRecord[]>([])
const total = ref(0)
const loadError = ref(false)

const queryParams = ref<DedupRecordQueryParams>({
  page: 1,
  page_size: 20,
  task_id: undefined,
  question_id: undefined,
  decision: undefined,
  needs_manual_review: undefined,
})

// 对比弹窗
const compareVisible = ref(false)
const compareRecord = ref<DedupRecord | null>(null)

// 人工复核弹窗
const resolveVisible = ref(false)
const resolveRecord = ref<DedupRecord | null>(null)
const resolveConclusion = ref<ManualResolution | ''>('')
const resolveReason = ref('')
const resolveSubmitting = ref(false)

const hasFilters = computed(() =>
  !!(
    queryParams.value.task_id ||
    queryParams.value.question_id ||
    queryParams.value.decision ||
    queryParams.value.needs_manual_review !== null
  ),
)

// 可人工复核的条件：decision=uncertain 且 manual_resolution=null
function canResolve(record: DedupRecord): boolean {
  return record.decision === 'uncertain' && record.manual_resolution === null
}

async function fetchData() {
  loading.value = true
  loadError.value = false
  try {
    const params: DedupRecordQueryParams = { ...queryParams.value }
    if (!params.task_id) delete params.task_id
    if (!params.question_id) delete params.question_id
    if (!params.decision) delete params.decision
    if (params.needs_manual_review === undefined || params.needs_manual_review === null) {
      delete params.needs_manual_review
    }

    const res = await getDedupRecords(params)
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
    needs_manual_review: undefined,
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

function openCompare(record: DedupRecord) {
  compareRecord.value = record
  compareVisible.value = true
}

function openResolve(record: DedupRecord) {
  resolveRecord.value = record
  resolveConclusion.value = ''
  resolveReason.value = ''
  resolveVisible.value = true
}

async function handleResolveSubmit() {
  if (!resolveRecord.value) return

  if (!resolveConclusion.value) {
    ElMessage.warning('请选择裁定结论')
    return
  }

  const trimmed = resolveReason.value.trim()
  if (!trimmed) {
    ElMessage.warning('请填写处理理由')
    return
  }
  if (trimmed.length > 1000) {
    ElMessage.warning('处理理由不能超过 1000 字符')
    return
  }

  resolveSubmitting.value = true
  try {
    await resolveDedupRecord(resolveRecord.value.id, {
      conclusion: resolveConclusion.value,
      reason: trimmed,
    })
    ElMessage.success('裁定成功')
    resolveVisible.value = false
    await fetchData()
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : ''
    // 40901 并发冲突：已被其他管理员处理
    if (msg.includes('40901') || msg.includes('已被') || msg.includes('并发')) {
      ElMessage.warning('该记录可能已被其他管理员处理，正在刷新...')
      resolveVisible.value = false
      await fetchData()
    } else if (msg.includes('40401')) {
      ElMessage.error('记录已不存在，正在刷新...')
      resolveVisible.value = false
      await fetchData()
    } else {
      // 其他错误：保留弹窗内容供修正
      ElMessage.error(msg || '裁定失败，请检查输入后重试')
    }
  } finally {
    resolveSubmitting.value = false
  }
}

function goToQuestion(id: number) {
  router.push(`/question-management/questions/${id}`)
}

function goToTask(taskId: number) {
  router.push(`/question-management/tasks/${taskId}`)
}

onMounted(() => {
  const taskParam = route.query.task_id
  const decisionParam = route.query.decision
  const manualParam = route.query.needs_manual_review

  if (taskParam) queryParams.value.task_id = Number(taskParam)
  if (decisionParam) queryParams.value.decision = decisionParam as DedupDecision
  if (manualParam === '1') queryParams.value.needs_manual_review = true

  fetchData()
})
</script>

<template>
  <div class="page-container">
    <div class="page-header">
      <div>
        <h2>去重疑点</h2>
        <p class="description">查看题目去重判定审计记录，人工裁定疑似重复题</p>
      </div>
    </div>

    <!-- 索引状态 -->
    <DedupStatusCard />

    <!-- 筛选 -->
    <div class="filter-toolbar" style="margin-top: 16px;">
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
        placeholder="自动判定"
        clearable
        style="width: 130px;"
        @change="handleFilterChange"
      >
        <el-option label="确认重复" value="duplicate" />
        <el-option label="不重复" value="distinct" />
        <el-option label="待人工复核" value="uncertain" />
      </el-select>
      <el-select
        v-model="queryParams.needs_manual_review"
        placeholder="复核状态"
        clearable
        style="width: 130px;"
        @change="handleFilterChange"
      >
        <el-option label="待人工复核" :value="true" />
        <el-option label="已处理" :value="false" />
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
        <p class="description">无法获取去重记录，请检查后端服务后重试</p>
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
        <p class="title">{{ hasFilters ? '筛选条件下暂无记录' : '暂无去重记录' }}</p>
        <p class="description">
          {{ hasFilters ? '请调整筛选条件后重试' : '当题目生成产生重复判定时，记录会自动出现在这里' }}
        </p>
      </div>
    </div>

    <!-- 表格 -->
    <div v-else class="card">
      <el-table :data="tableData" style="width: 100%;">
        <el-table-column prop="id" label="记录ID" width="80" align="center" />
        <el-table-column label="最终结论" width="110" align="center">
          <template #default="{ row }">
            <span :class="['status-badge', `status-badge--${getDecisionClass(row.effective_decision)}`]">
              {{ getDecisionLabel(row.effective_decision) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="自动判定" width="110" align="center">
          <template #default="{ row }">
            <span :class="['status-badge', `status-badge--${getDecisionClass(row.decision)}`]">
              {{ getDecisionLabel(row.decision) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="人工裁定" width="110" align="center">
          <template #default="{ row }">
            <span v-if="row.manual_resolution" :class="['status-badge', `status-badge--${getManualResolutionClass(row.manual_resolution)}`]">
              {{ getManualResolutionLabel(row.manual_resolution) }}
            </span>
            <span v-else-if="row.needs_manual_review" class="status-badge status-badge--warning">待复核</span>
            <span v-else class="muted-text">-</span>
          </template>
        </el-table-column>
        <el-table-column label="新题快照" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">
            <div class="snapshot-text">{{ row.new_content_snapshot }}</div>
            <div class="snapshot-meta">
              {{ QUESTION_TYPE_LABELS[row.new_question_type] || row.new_question_type }}
            </div>
          </template>
        </el-table-column>
        <el-table-column label="匹配历史题" width="110" align="center">
          <template #default="{ row }">
            <el-link
              v-if="row.matched_question_id"
              type="primary"
              @click.stop="goToQuestion(row.matched_question_id)"
            >
              #{{ row.matched_question_id }}
            </el-link>
            <span v-else class="muted-text">批次内</span>
          </template>
        </el-table-column>
        <el-table-column label="相似度分数" width="110" align="center">
          <template #default="{ row }">
            <div class="score-cell">
              <div>{{ formatScore(row.algorithm_score) }}</div>
              <div class="score-sub" v-if="row.vector_score > 0">
                向量 {{ formatScore(row.vector_score) }}
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="判定方式" width="120" align="center">
          <template #default="{ row }">
            <span class="method-tag">{{ getMethodLabel(row.decision_method) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="任务" width="80" align="center">
          <template #default="{ row }">
            <el-link v-if="row.task_id" type="primary" @click.stop="goToTask(row.task_id)">
              #{{ row.task_id }}
            </el-link>
            <span v-else class="muted-text">-</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right" align="center">
          <template #default="{ row }">
            <el-button text type="primary" size="small" @click="openCompare(row)">
              <Eye :size="14" style="margin-right: 4px;" />
              对比
            </el-button>
            <el-button
              v-if="canResolve(row)"
              text
              type="warning"
              size="small"
              @click="openResolve(row)"
            >
              <Scale :size="14" style="margin-right: 4px;" />
              人工复核
            </el-button>
            <el-button
              v-if="row.matched_question_id"
              text
              type="primary"
              size="small"
              @click="goToQuestion(row.matched_question_id)"
            >
              <ArrowRight :size="14" style="margin-right: 4px;" />
              原题
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

    <!-- 对比弹窗 -->
    <el-dialog
      v-model="compareVisible"
      title="新旧题对比"
      width="800px"
      :close-on-click-modal="false"
    >
      <div v-if="compareRecord" class="compare-container">
        <!-- 最终结论与人工裁定 -->
        <div class="compare-info" style="order: -1;">
          <div class="info-grid">
            <div class="info-item">
              <span class="info-label">最终结论</span>
              <span :class="['status-badge', `status-badge--${getDecisionClass(compareRecord.effective_decision)}`]">
                {{ getDecisionLabel(compareRecord.effective_decision) }}
              </span>
            </div>
            <div class="info-item">
              <span class="info-label">自动判定</span>
              <span :class="['status-badge', `status-badge--${getDecisionClass(compareRecord.decision)}`]">
                {{ getDecisionLabel(compareRecord.decision) }}
              </span>
            </div>
            <div class="info-item">
              <span class="info-label">人工裁定</span>
              <span v-if="compareRecord.manual_resolution" :class="['status-badge', `status-badge--${getManualResolutionClass(compareRecord.manual_resolution)}`]">
                {{ getManualResolutionLabel(compareRecord.manual_resolution) }}
              </span>
              <span v-else class="muted-text">未裁定</span>
            </div>
          </div>

          <!-- 已裁定详情 -->
          <div v-if="compareRecord.manual_resolution" class="resolution-detail">
            <div class="resolution-row">
              <UserCheck :size="14" />
              <span>处理管理员：#{{ compareRecord.resolved_by }}</span>
            </div>
            <div class="resolution-row">
              <span class="info-label">处理时间：</span>
              {{ compareRecord.resolved_at ? new Date(compareRecord.resolved_at).toLocaleString('zh-CN') : '-' }}
            </div>
            <div class="resolution-row">
              <span class="info-label">处理理由：</span>
              {{ compareRecord.resolution_reason }}
            </div>
          </div>
        </div>

        <!-- 新题 -->
        <div class="compare-section">
          <div class="compare-header">
            <span class="compare-label">新生成题目</span>
            <span class="compare-meta">
              {{ QUESTION_TYPE_LABELS[compareRecord.new_question_type] || compareRecord.new_question_type }}
              <span v-if="compareRecord.new_question_bank_id"> · 题库#{{ compareRecord.new_question_bank_id }}</span>
            </span>
          </div>
          <pre class="compare-content">{{ compareRecord.new_content_snapshot }}</pre>
          <div v-if="compareRecord.new_knowledge_ids && compareRecord.new_knowledge_ids.length > 0" class="compare-knowledge">
            知识点：{{ compareRecord.new_knowledge_ids.join(', ') }}
          </div>
        </div>

        <!-- 匹配历史题 -->
        <div class="compare-section">
          <div class="compare-header">
            <span class="compare-label">匹配历史题目</span>
            <span class="compare-meta" v-if="compareRecord.matched_question_id">
              题目 #{{ compareRecord.matched_question_id }}
              <el-link type="primary" size="small" @click="goToQuestion(compareRecord.matched_question_id)">
                查看详情
              </el-link>
            </span>
            <span v-else class="compare-meta">批次内新题</span>
          </div>
          <div v-if="compareRecord.matched_question_id" class="compare-hint">
            点击"查看详情"可查看完整历史题目内容（题干、选项、答案、解析）。
          </div>
          <div v-else class="compare-hint">
            此记录为批次内新题之间的比对，无外部历史题目。
          </div>
          <div v-if="compareRecord.matched_knowledge_ids && compareRecord.matched_knowledge_ids.length > 0" class="compare-knowledge">
            知识点：{{ compareRecord.matched_knowledge_ids.join(', ') }}
          </div>
        </div>

        <!-- 自动判定证据 -->
        <div class="compare-info">
          <div class="info-grid">
            <div class="info-item">
              <span class="info-label">判定方式</span>
              <span>{{ getMethodLabel(compareRecord.decision_method) }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">范围</span>
              <span>{{ getScopeModeLabel(compareRecord.scope_mode) }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">相似度分数</span>
              <span>{{ formatScore(compareRecord.algorithm_score) }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">关键词分数</span>
              <span>{{ formatScore(compareRecord.keyword_score) }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">向量分数</span>
              <span>{{ formatScore(compareRecord.vector_score) }}</span>
            </div>
            <div class="info-item" v-if="compareRecord.llm_called">
              <span class="info-label">LLM 结论</span>
              <span>{{ getDecisionLabel(compareRecord.llm_decision || '') }}</span>
            </div>
            <div class="info-item" v-if="compareRecord.llm_reason">
              <span class="info-label">LLM 理由</span>
              <span class="llm-reason">{{ compareRecord.llm_reason }}</span>
            </div>
          </div>
          <div class="compare-note">
            相似度分数为算法分数，非重复概率。自动判定结论由后端算法/LLM 产生，前端不重新计算。
          </div>
        </div>

        <!-- 操作 -->
        <div v-if="canResolve(compareRecord)" class="compare-actions">
          <el-button type="warning" @click="openResolve(compareRecord)">
            <Scale :size="16" style="margin-right: 4px;" />
            人工复核
          </el-button>
        </div>
      </div>
    </el-dialog>

    <!-- 人工复核弹窗 -->
    <el-dialog
      v-model="resolveVisible"
      title="人工复核裁定"
      width="700px"
      :close-on-click-modal="false"
    >
      <div v-if="resolveRecord" class="resolve-container">
        <!-- 新题快照 -->
        <div class="resolve-section">
          <div class="resolve-section-title">新题快照</div>
          <div class="resolve-snapshot">
            <div class="resolve-meta">
              {{ QUESTION_TYPE_LABELS[resolveRecord.new_question_type] || resolveRecord.new_question_type }}
              <span v-if="resolveRecord.new_question_bank_id"> · 题库#{{ resolveRecord.new_question_bank_id }}</span>
            </div>
            <pre class="resolve-content">{{ resolveRecord.new_content_snapshot }}</pre>
          </div>
        </div>

        <!-- 匹配历史题 -->
        <div class="resolve-section" v-if="resolveRecord.matched_question_id">
          <div class="resolve-section-title">匹配历史题 #{{ resolveRecord.matched_question_id }}</div>
          <div class="resolve-hint">
            <el-link type="primary" @click="goToQuestion(resolveRecord.matched_question_id)">
              查看历史题详情
            </el-link>
            <span class="muted-text" style="margin-left: 8px;">请在对比后做出判断</span>
          </div>
        </div>

        <!-- 自动判定证据 -->
        <div class="resolve-section">
          <div class="resolve-section-title">自动判定证据</div>
          <div class="resolve-evidence">
            <div class="evidence-item">
              <span class="evidence-label">自动判定</span>
              <span :class="['status-badge', `status-badge--${getDecisionClass(resolveRecord.decision)}`]">
                {{ getDecisionLabel(resolveRecord.decision) }}
              </span>
            </div>
            <div class="evidence-item">
              <span class="evidence-label">判定方式</span>
              <span>{{ getMethodLabel(resolveRecord.decision_method) }}</span>
            </div>
            <div class="evidence-item">
              <span class="evidence-label">相似度分数</span>
              <span>{{ formatScore(resolveRecord.algorithm_score) }}</span>
            </div>
            <div class="evidence-item" v-if="resolveRecord.llm_called">
              <span class="evidence-label">LLM 结论</span>
              <span>{{ getDecisionLabel(resolveRecord.llm_decision || '') }}</span>
            </div>
            <div class="evidence-item" v-if="resolveRecord.llm_reason" style="grid-column: span 2;">
              <span class="evidence-label">LLM 理由</span>
              <span>{{ resolveRecord.llm_reason }}</span>
            </div>
          </div>
        </div>

        <!-- 人工裁定 -->
        <div class="resolve-section">
          <div class="resolve-section-title">人工裁定 <span class="required">*</span></div>
          <el-radio-group v-model="resolveConclusion" class="conclusion-group">
            <el-radio value="duplicate" class="conclusion-radio">
              <span class="conclusion-label error-text">确认重复</span>
              <span class="conclusion-desc">新题与历史题内容重复，保留历史题</span>
            </el-radio>
            <el-radio value="distinct" class="conclusion-radio">
              <span class="conclusion-label success-text">确认不重复</span>
              <span class="conclusion-desc">新题与历史题不同，疑点排除</span>
            </el-radio>
          </el-radio-group>

          <div class="reason-section">
            <div class="reason-label">处理理由 <span class="required">*</span></div>
            <el-input
              v-model="resolveReason"
              type="textarea"
              :rows="3"
              maxlength="1000"
              show-word-limit
              placeholder="请填写裁定理由（1~1000 字符），例如：与历史题考查内容和正确答案一致，保留历史题。"
            />
          </div>

          <div class="resolve-warning">
            人工裁定只更新去重审计结论，不会自动驳回或发布题目。如需驳回新题，请在题目审核页面操作。
          </div>
        </div>
      </div>

      <template #footer>
        <el-button @click="resolveVisible = false">取消</el-button>
        <el-button
          type="primary"
          :loading="resolveSubmitting"
          :disabled="!resolveConclusion || !resolveReason.trim()"
          @click="handleResolveSubmit"
        >
          提交裁定
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.filter-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 16px;
}

.snapshot-text {
  font-size: 13px;
  line-height: 1.5;
  color: var(--color-foreground);
}

.snapshot-meta {
  font-size: 11px;
  color: var(--color-muted-foreground);
  margin-top: 2px;
}

.score-cell {
  text-align: center;
}

.score-sub {
  font-size: 11px;
  color: var(--color-muted-foreground);
  margin-top: 2px;
}

.method-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  background: var(--color-muted);
  color: var(--color-foreground);
}

.muted-text {
  color: var(--color-muted-foreground);
  font-size: 12px;
}

/* 对比弹窗 */
.compare-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.compare-section {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 16px;
}

.compare-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.compare-label {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-foreground);
}

.compare-meta {
  font-size: 12px;
  color: var(--color-muted-foreground);
  display: flex;
  align-items: center;
  gap: 6px;
}

.compare-content {
  margin: 0;
  font-family: inherit;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 14px;
  line-height: 1.7;
  color: var(--color-foreground);
  background: var(--color-muted);
  padding: 12px;
  border-radius: var(--radius-md);
}

.compare-hint {
  font-size: 13px;
  color: var(--color-muted-foreground);
  padding: 8px 0;
}

.compare-knowledge {
  margin-top: 8px;
  font-size: 12px;
  color: var(--color-muted-foreground);
}

.compare-info {
  background: var(--color-muted);
  border-radius: var(--radius-md);
  padding: 16px;
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

.llm-reason {
  font-size: 12px;
  line-height: 1.5;
  color: var(--color-foreground);
  grid-column: span 3;
}

.compare-note {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--color-border);
  font-size: 12px;
  color: var(--color-muted-foreground);
}

.resolution-detail {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--color-border);
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.resolution-row {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--color-foreground);
}

.compare-actions {
  display: flex;
  justify-content: flex-end;
}

/* 人工复核弹窗 */
.resolve-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.resolve-section {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 16px;
}

.resolve-section-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-foreground);
  margin-bottom: 10px;
}

.required {
  color: var(--color-error, #DC2626);
}

.resolve-meta {
  font-size: 12px;
  color: var(--color-muted-foreground);
  margin-bottom: 6px;
}

.resolve-content {
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

.resolve-hint {
  font-size: 13px;
}

.resolve-evidence {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
}

.evidence-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}

.evidence-label {
  font-size: 12px;
  color: var(--color-muted-foreground);
  min-width: 70px;
}

.conclusion-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}

.conclusion-radio {
  width: 100%;
  height: auto;
  padding: 10px 12px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  margin: 0 !important;
}

.conclusion-radio.is-checked {
  border-color: var(--color-primary, #1E40AF);
  background: #F0F7FF;
}

.conclusion-label {
  font-weight: 600;
  margin-right: 8px;
}

.error-text { color: var(--color-error, #DC2626); }
.success-text { color: var(--color-success, #059669); }

.conclusion-desc {
  font-size: 12px;
  color: var(--color-muted-foreground);
}

.reason-section {
  margin-top: 12px;
}

.reason-label {
  font-size: 13px;
  font-weight: 500;
  color: var(--color-foreground);
  margin-bottom: 6px;
}

.resolve-warning {
  margin-top: 12px;
  padding: 10px 12px;
  background: #FFFBEB;
  border-radius: var(--radius-md);
  font-size: 12px;
  color: #92400E;
  line-height: 1.5;
}
</style>
