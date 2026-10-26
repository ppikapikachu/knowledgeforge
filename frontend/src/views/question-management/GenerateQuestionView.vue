<script setup lang="ts">
/**
 * AI 生成题目（manual/auto 双模式）
 * 后端契约（实际后端 Schema）：
 *   POST /question-generation/tasks
 *   POST /question-generation/allocations/preview
 *
 * question_type: "SINGLE_CHOICE"（大写），difficulty: 1|2|3（整数），count: 1~500
 * 预览响应: allocatable_count（非 allocated_count），allocations（非 items）
 */
import { ref, onMounted, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { createGenerationTaskWithAllocation, previewAllocation } from '@/api/questionDemand'
import { getQuestionBankList } from '@/api/questionBank'
import { useQuestionLookups } from '@/composables/useQuestionLookups'
import type { QuestionBank } from '@/types/questionManagement'
import type { Knowledge } from '@/types/knowledge'
import type { AllocationPreviewData, AllocationPreviewItem, AllocationMode } from '@/types/questionDemand'
import {
  QUESTION_TYPES,
  DIFFICULTY_LABELS,
  QUESTION_TYPE_LABELS,
} from '@/constants/questionManagement'
import {
  IMPORTANCE_LABELS,
  IMPORTANCE_CLASSES,
  formatScore,
} from '@/constants/questionDemand'
import { ElMessage, ElMessageBox } from 'element-plus'
import DedupStatusCard from '@/components/question-management/DedupStatusCard.vue'
import {
  Sparkles,
  ArrowLeft,
  ListChecks,
  Eye,
  Settings,
  CheckCircle,
  AlertTriangle,
} from 'lucide-vue-next'

const router = useRouter()
const { searchKnowledge } = useQuestionLookups()

const banks = ref<QuestionBank[]>([])
const banksLoading = ref(false)
const knowledgeOptions = ref<Knowledge[]>([])
const knowledgeLoading = ref(false)

const submitting = ref(false)
const previewLoading = ref(false)
const previewData = ref<AllocationPreviewData | null>(null)
const previewInvalidated = ref(false)

// 分配模式
const allocationMode = ref<AllocationMode>('manual')

// AI 自动审核开关（默认关闭，每次创建任务由管理员明确决定）
const enableAiReview = ref(false)

const form = ref({
  question_bank_id: undefined as number | undefined,
  knowledge_id: undefined as number | undefined,
  question_type: 'SINGLE_CHOICE',
  difficulty: 2,
  count: 5,
})

const isManual = computed(() => allocationMode.value === 'manual')
const isAuto = computed(() => allocationMode.value === 'auto')

const bankName = computed(() =>
  banks.value.find((b) => b.id === form.value.question_bank_id)?.name || '',
)

// 预览参数摘要
const previewValid = computed(() =>
  !!previewData.value && !previewInvalidated.value,
)

async function loadBanks() {
  banksLoading.value = true
  try {
    const res = await getQuestionBankList({ page: 1, page_size: 100 })
    banks.value = res.data.items
  } catch {
    ElMessage.error('题库列表加载失败')
  } finally {
    banksLoading.value = false
  }
}

async function handleKnowledgeSearch(keyword: string) {
  knowledgeLoading.value = true
  try {
    knowledgeOptions.value = await searchKnowledge(keyword)
  } catch {
    ElMessage.error('知识点搜索失败')
  } finally {
    knowledgeLoading.value = false
  }
}

// 参数变化时使预览失效
function invalidatePreview() {
  previewData.value = null
  previewInvalidated.value = true
}

watch(
  () => [form.value.question_bank_id, form.value.question_type, form.value.difficulty, form.value.count],
  () => {
    if (isAuto.value) invalidatePreview()
  },
)

function handleModeChange(mode: AllocationMode) {
  allocationMode.value = mode
  invalidatePreview()
  if (mode === 'manual') {
    form.value.knowledge_id = undefined
    handleKnowledgeSearch('')
  }
}

// ---- 校验 ----
function validate(): string | null {
  const f = form.value
  if (!f.question_bank_id) return '请选择目标题库'
  if (!f.question_type) return '请选择题型'
  if (![1, 2, 3].includes(f.difficulty)) return '请选择难度'
  const n = Number(f.count)
  if (!Number.isInteger(n) || n < 1 || n > 500) return '生成数量必须是 1~500 的整数'
  if (isManual.value && !f.knowledge_id) return '请在指定知识点模式下选择一个知识点'
  return null
}

// ---- 智能分配预览 ----
async function handlePreview() {
  const err = validate()
  if (err) {
    ElMessage.warning(err)
    return
  }

  previewLoading.value = true
  previewInvalidated.value = false
  try {
    const res = await previewAllocation({
      question_bank_id: form.value.question_bank_id!,
      question_type: form.value.question_type,
      difficulty: form.value.difficulty,
      count: Number(form.value.count),
    })
    previewData.value = res.data
  } catch (e) {
    previewData.value = null
    const msg = e instanceof Error ? e.message : ''
    if (msg.includes('POLICY_DISABLED') || msg.includes('QUESTION_DEMAND_POLICY_DISABLED')) {
      ElMessage.error('智能分配策略已停用，请到「出题策略」页面启用后重试')
    } else if (msg.includes('NO_ELIGIBLE_KNOWLEDGE_POINTS')) {
      ElMessage.error('当前题库没有符合条件的候选知识点，请检查「题库知识范围」配置')
    } else {
      ElMessage.error(msg || '预览失败')
    }
  } finally {
    previewLoading.value = false
  }
}

// ---- 创建任务（manual） ----
async function handleCreateManual() {
  const err = validate()
  if (err) {
    ElMessage.warning(err)
    return
  }

  const f = form.value
  const knName = knowledgeOptions.value.find((k) => k.id === f.knowledge_id)?.name || `#${f.knowledge_id}`

  try {
    await ElMessageBox.confirm(
      `即将创建 AI 出题任务（指定知识点模式）：\n题库：${bankName.value}\n知识点：${knName}\n题型：${QUESTION_TYPE_LABELS[f.question_type]}\n难度：${DIFFICULTY_LABELS[f.difficulty]}\n数量：${f.count}`,
      '参数确认',
      { confirmButtonText: '开始生成', cancelButtonText: '返回修改', type: 'info' },
    )
  } catch {
    return
  }

  submitting.value = true
  try {
    const res = await createGenerationTaskWithAllocation({
      allocation_mode: 'manual',
      knowledge_id: f.knowledge_id!,
      question_bank_id: f.question_bank_id!,
      question_type: f.question_type,
      difficulty: f.difficulty,
      count: Number(f.count),
      enable_ai_review: enableAiReview.value,
    })
    ElMessage.success(res.data?.message || '任务已创建')
    router.push(`/question-management/tasks/${res.data?.task_id}`)
  } catch (e) {
    const msg = e instanceof Error ? e.message : ''
    if (msg.includes('timeout') || msg.includes('超时')) {
      ElMessage.warning('请求超时，任务可能已在后台创建，请先到「生成任务」列表核实，不要重复提交')
    }
  } finally {
    submitting.value = false
  }
}

// ---- 创建任务（auto） ----
async function handleCreateAuto() {
  if (!previewValid.value || !previewData.value) {
    ElMessage.warning('请先预览分配方案')
    return
  }

  const pv = previewData.value
  const allocated = pv.allocatable_count
  const requested = pv.requested_count
  const unallocated = pv.unallocated_count

  if (allocated <= 0) {
    ElMessage.error('当前无可分配的知识点，无法创建任务')
    return
  }

  // 部分分配确认
  let allowPartial = false
  if (unallocated > 0) {
    try {
      await ElMessageBox.confirm(
        `目标 ${requested} 道，当前可分配 ${allocated} 道，尚有 ${unallocated} 道无法分配。\n` +
        `创建任务将按后端当前可分配的 ${allocated} 道生成。\n\n` +
        `确认创建任务？`,
        '部分分配确认',
        { confirmButtonText: `确认创建（${allocated} 道）`, cancelButtonText: '取消', type: 'warning' },
      )
      allowPartial = true
    } catch {
      return // 取消不调用创建
    }
  } else {
    try {
      await ElMessageBox.confirm(
        `即将创建 AI 出题任务（系统智能分配模式）：\n题库：${bankName.value}\n题型：${QUESTION_TYPE_LABELS[form.value.question_type]}\n难度：${DIFFICULTY_LABELS[form.value.difficulty]}\n数量：${requested}`,
        '参数确认',
        { confirmButtonText: '开始生成', cancelButtonText: '返回修改', type: 'info' },
      )
    } catch {
      return
    }
    allowPartial = false
  }

  submitting.value = true
  try {
    const res = await createGenerationTaskWithAllocation({
      allocation_mode: 'auto',
      question_bank_id: form.value.question_bank_id!,
      question_type: form.value.question_type,
      difficulty: form.value.difficulty,
      count: Number(form.value.count),
      allow_partial: allowPartial,
      enable_ai_review: enableAiReview.value,
    })
    ElMessage.success(res.data?.message || '任务已创建')
    router.push(`/question-management/tasks/${res.data?.task_id}`)
  } catch (e) {
    const msg = e instanceof Error ? e.message : ''
    if (msg.includes('ALLOCATION_INSUFFICIENT')) {
      ElMessage.error('分配不足，请重新预览或减少生成数量')
      invalidatePreview()
    } else if (msg.includes('NO_ELIGIBLE_KNOWLEDGE_POINTS')) {
      ElMessage.error('无候选知识点，请检查知识范围和策略配置')
      invalidatePreview()
    } else if (msg.includes('timeout') || msg.includes('超时')) {
      ElMessage.warning('请求超时，任务可能已在后台创建，请先到「生成任务」列表核实，不要重复提交')
    }
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  loadBanks()
  handleKnowledgeSearch('')
})
</script>

<template>
  <div class="page-container">
    <div class="page-header">
      <div>
        <h2>AI 生成题目</h2>
        <p class="description">
          支持指定知识点和系统智能分配两种模式。生成结果需在「题目审核」中人工审核后才会发布。
        </p>
      </div>
      <div class="header-actions">
        <el-button @click="router.push('/question-management/policies')">
          <Settings :size="16" style="margin-right: 4px;" />
          出题策略
        </el-button>
        <el-button @click="router.push('/question-management/tasks')">
          <ListChecks :size="16" style="margin-right: 4px;" />
          生成任务
        </el-button>
      </div>
    </div>

    <!-- 分配模式选择 -->
    <div class="card">
      <div class="card-body">
        <div class="mode-label">分配方式</div>
        <el-radio-group :model-value="allocationMode" @update:model-value="(v: AllocationMode) => handleModeChange(v)" class="mode-group">
          <el-radio-button value="manual">指定知识点</el-radio-button>
          <el-radio-button value="auto">系统智能分配</el-radio-button>
        </el-radio-group>
        <div class="mode-desc">
          {{ isManual
            ? '由管理员明确指定一个知识点，生成针对该知识点的题目。'
            : '由系统根据库存、近期使用情况和知识点重要程度，自动分配多个知识点。需要题库已配置知识范围。'
          }}
        </div>
      </div>
    </div>

    <!-- 语义去重状态 -->
    <div style="margin-top: 16px;">
      <DedupStatusCard />
    </div>

    <!-- 表单 -->
    <div class="card" style="margin-top: 16px;">
      <div class="card-body">
        <el-form :model="form" label-width="130px" label-position="right" style="max-width: 680px;">
          <el-form-item label="目标题库" required>
            <el-select
              v-model="form.question_bank_id"
              placeholder="选择题库"
              filterable
              :loading="banksLoading"
              style="width: 100%;"
            >
              <el-option v-for="b in banks" :key="b.id" :label="b.name" :value="b.id">
                <span>{{ b.name }}</span>
                <span class="option-sub">（{{ b.question_count }} 题）</span>
              </el-option>
            </el-select>
          </el-form-item>

          <!-- manual 模式：知识点选择 -->
          <el-form-item v-if="isManual" label="知识点" required>
            <el-select
              v-model="form.knowledge_id"
              placeholder="搜索并选择知识点"
              filterable
              remote
              :remote-method="handleKnowledgeSearch"
              :loading="knowledgeLoading"
              style="width: 100%;"
            >
              <el-option v-for="k in knowledgeOptions" :key="k.id" :label="k.name" :value="k.id" />
            </el-select>
            <div class="field-hint">生成题目将归入所选题库，并关联所选知识点</div>
          </el-form-item>

          <el-form-item label="题型" required>
            <el-select v-model="form.question_type" style="width: 200px;">
              <el-option v-for="t in QUESTION_TYPES" :key="t.value" :label="t.label" :value="t.value" />
            </el-select>
          </el-form-item>

          <el-form-item label="难度" required>
            <el-radio-group v-model="form.difficulty">
              <el-radio-button :value="1">简单</el-radio-button>
              <el-radio-button :value="2">中等</el-radio-button>
              <el-radio-button :value="3">困难</el-radio-button>
            </el-radio-group>
          </el-form-item>

          <el-form-item :label="isAuto ? '期望生成总量' : '生成数量'" required>
            <el-input-number v-model="form.count" :min="1" :max="500" :step="1" />
            <div class="field-hint">1 ~ 500，由后端校验</div>
          </el-form-item>

          <!-- AI 自动审核开关 -->
          <el-form-item label="AI 自动审核">
            <div class="ai-review-toggle">
              <el-switch v-model="enableAiReview" />
              <span class="ai-review-label">
                {{ enableAiReview ? '已启用' : '默认关闭' }}
              </span>
            </div>
            <div class="ai-review-hint">
              开启后，题目完成去重并满足审核准入条件时，系统将调用 AI 进行质量审核。
              符合条件的客观题可能自动发布；存在明确严重缺陷的题目可能自动驳回；
              无法确定、去重疑点、简答题或审核失败的题目仍保留在人工审核队列。
            </div>
            <div class="ai-review-warnings">
              <div class="warn-item">⚠ 自动通过会将题目状态变为「已发布」</div>
              <div class="warn-item">⚠ 自动驳回会将题目软驳回为「已驳回」，不会删除数据</div>
              <div class="warn-item">⚠ 简答题会跳过 AI 审核，继续人工审核</div>
              <div class="warn-item">⚠ 自动审核受服务端总开关控制，未启用时提交会被拒绝</div>
            </div>
          </el-form-item>

          <!-- 操作按钮 -->
          <el-form-item>
            <template v-if="isAuto">
              <el-button
                type="primary"
                size="large"
                :loading="previewLoading"
                @click="handlePreview"
              >
                <Eye :size="16" style="margin-right: 4px;" />
                预览分配
              </el-button>
              <el-button
                v-if="previewValid && previewData && previewData.allocatable_count > 0"
                type="success"
                size="large"
                :loading="submitting"
                @click="handleCreateAuto"
              >
                <Sparkles :size="16" style="margin-right: 4px;" />
                创建任务
              </el-button>
            </template>
            <el-button
              v-else
              type="primary"
              size="large"
              :loading="submitting"
              @click="handleCreateManual"
            >
              <Sparkles :size="16" style="margin-right: 4px;" />
              开始生成
            </el-button>
            <el-button size="large" @click="router.back()">
              <ArrowLeft :size="16" style="margin-right: 4px;" />
              返回
            </el-button>
          </el-form-item>
        </el-form>
      </div>
    </div>

    <!-- 预览结果 -->
    <template v-if="isAuto && previewData">
      <div class="card preview-card" :class="{ invalidated: previewInvalidated }">
        <div class="card-header">
          分配预览结果
          <span v-if="previewInvalidated" class="invalid-hint">（参数已修改，请重新预览）</span>
        </div>
        <div class="card-body">
          <!-- 汇总 -->
          <div class="preview-summary">
            <div class="summary-item">
              <div class="summary-value">{{ previewData.requested_count }}</div>
              <div class="summary-label">目标数量</div>
            </div>
            <div class="summary-item">
              <div class="summary-value ok">{{ previewData.allocatable_count }}</div>
              <div class="summary-label">可分配</div>
            </div>
            <div class="summary-item">
              <div class="summary-value" :class="previewData.unallocated_count > 0 ? 'warn' : ''">
                {{ previewData.unallocated_count }}
              </div>
              <div class="summary-label">无法分配</div>
            </div>
          </div>

          <!-- 警告 -->
          <div v-if="previewData.warnings.length > 0" class="preview-warnings">
            <div v-for="(w, i) in previewData.warnings" :key="i" class="warning-item">
              <AlertTriangle :size="14" />
              {{ w }}
            </div>
          </div>

          <!-- 空分配 -->
          <div v-if="previewData.allocations.length === 0" class="preview-empty">
            当前没有符合条件的候选知识点，请检查知识范围和策略配置。
          </div>

          <!-- 分配明细 -->
          <div v-else class="preview-table-wrapper">
            <el-table :data="previewData.allocations" style="width: 100%;" size="small">
              <el-table-column prop="knowledge_name" label="知识点" min-width="180" show-overflow-tooltip />
              <el-table-column label="重要程度" width="110" align="center">
                <template #default="{ row }">
                  <span :class="['status-badge', `status-badge--${IMPORTANCE_CLASSES[row.importance_level] || 'muted'}`]">
                    {{ IMPORTANCE_LABELS[row.importance_level] || row.importance_level }}
                  </span>
                </template>
              </el-table-column>
              <el-table-column label="需求分数" width="100" align="center">
                <template #default="{ row }">
                  {{ formatScore(row.demand_score) }}
                </template>
              </el-table-column>
              <el-table-column prop="demand_count" label="需求数量" width="90" align="center" />
              <el-table-column prop="allocated_count" label="分配数量" width="90" align="center">
                <template #default="{ row }">
                  <strong style="color: var(--color-primary, #1E40AF);">{{ row.allocated_count }}</strong>
                </template>
              </el-table-column>
              <el-table-column label="分配进度" width="120" align="center">
                <template #default="{ row }">
                  <el-progress
                    :percentage="previewData ? Math.round((row.allocated_count / previewData.requested_count) * 100) : 0"
                    :stroke-width="6"
                    :show-text="false"
                    style="width: 80px;"
                  />
                </template>
              </el-table-column>
            </el-table>
          </div>

          <!-- 策略快照 -->
          <div class="policy-snapshot">
            <div class="snapshot-title">策略版本：v{{ previewData.policy_version ?? '-' }}</div>
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

.mode-label {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-foreground);
  margin-bottom: 8px;
}

.mode-group {
  margin-bottom: 8px;
}

.mode-desc {
  font-size: 13px;
  color: var(--color-muted-foreground);
  line-height: 1.5;
}

.field-hint {
  font-size: 12px;
  color: var(--color-muted-foreground, #9CA3AF);
  margin-top: 4px;
}

.ai-review-toggle {
  display: flex;
  align-items: center;
  gap: 10px;
}

.ai-review-label {
  font-size: 14px;
  font-weight: 500;
  color: var(--color-foreground);
}

.ai-review-hint {
  margin-top: 8px;
  font-size: 12px;
  line-height: 1.6;
  color: var(--color-muted-foreground);
  max-width: 680px;
}

.ai-review-warnings {
  margin-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.ai-review-warnings .warn-item {
  font-size: 12px;
  color: #92400E;
  background: #FFFBEB;
  padding: 3px 8px;
  border-radius: var(--radius-sm, 4px);
  width: fit-content;
}

.option-sub {
  float: right;
  font-size: 12px;
  color: var(--color-muted-foreground);
}

.preview-card {
  margin-top: 16px;
  transition: opacity 0.3s;
}

.preview-card.invalidated {
  opacity: 0.6;
}

.invalid-hint {
  font-size: 12px;
  color: var(--color-warning, #D97706);
  font-weight: 400;
  margin-left: 8px;
}

.preview-summary {
  display: flex;
  gap: 32px;
  padding: 16px;
  background: var(--color-muted);
  border-radius: var(--radius-md);
  margin-bottom: 16px;
}

.summary-item {
  text-align: center;
}

.summary-value {
  font-size: 28px;
  font-weight: 700;
  color: var(--color-foreground);
}

.summary-value.ok { color: var(--color-success, #059669); }
.summary-value.warn { color: var(--color-warning, #D97706); }

.summary-label {
  font-size: 13px;
  color: var(--color-muted-foreground);
  margin-top: 4px;
}

.preview-warnings {
  margin-bottom: 12px;
}

.warning-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  background: #FFFBEB;
  border-radius: var(--radius-md);
  font-size: 13px;
  color: #92400E;
  margin-bottom: 4px;
}

.preview-empty {
  padding: 24px;
  text-align: center;
  color: var(--color-muted-foreground);
  background: var(--color-muted);
  border-radius: var(--radius-md);
}

.preview-table-wrapper {
  margin-bottom: 12px;
}

.policy-snapshot {
  font-size: 12px;
  color: var(--color-muted-foreground);
}
</style>
