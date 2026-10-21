<script setup lang="ts">
/**
 * 题目详情 / 审核
 * GET /api/v1/questions/{id}
 * 编辑：PUT /api/v1/questions/{id}（后端有历史答题保护，核心字段被拒时展示后端提示）
 * 审核：POST /api/v1/question-generation/questions/{id}/review  { action: publish|reject, reason }
 * 下架：DELETE /api/v1/questions/{id}（软删除，状态变为 disabled）
 */
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getQuestionDetail, updateQuestion, deleteQuestion } from '@/api/question'
import { reviewQuestion } from '@/api/questionGeneration'
import { useQuestionLookups } from '@/composables/useQuestionLookups'
import type { Question, QuestionUpdateRequest } from '@/types/question'
import { QUESTION_STATUS, normalizeQuestionStatus } from '@/constants/questionManagement'
import { getQuestionDedupStatusLabel, QUESTION_DEDUP_STATUS_CLASSES } from '@/constants/questionDedup'
import QuestionPreview from '@/components/question-management/QuestionPreview.vue'
import QuestionForm from '@/components/question-management/QuestionForm.vue'
import QuestionStatusTag from '@/components/question-management/QuestionStatusTag.vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, Edit, CheckCircle, XCircle, Ban, Eye } from 'lucide-vue-next'

const route = useRoute()
const router = useRouter()
const { loadAll, bankName, knowledgeName } = useQuestionLookups()

const loading = ref(true)
const question = ref<Question | null>(null)
const loadError = ref(false)
const editing = ref(false)
const saving = ref(false)
const reviewing = ref(false)

const questionId = computed(() => Number(route.params.questionId))
const fromReview = computed(() => route.query.from === 'review')

// 后端状态大小写不一致（DISABLED 大写），统一归一化后比较
const normalizedStatus = computed(() =>
  question.value ? normalizeQuestionStatus(question.value.status) : '',
)
const isPendingReview = computed(() => normalizedStatus.value === QUESTION_STATUS.PENDING_REVIEW)
const isPublished = computed(() => normalizedStatus.value === QUESTION_STATUS.PUBLISHED)
const isRejected = computed(() => normalizedStatus.value === QUESTION_STATUS.REJECTED)
const isDisabled = computed(() => normalizedStatus.value === QUESTION_STATUS.DISABLED)

const knowledgeNames = computed(() => {
  if (!question.value) return []
  return (question.value.knowledge_ids || []).map((id) => knowledgeName(id))
})

async function fetchDetail() {
  loading.value = true
  loadError.value = false
  try {
    const res = await getQuestionDetail(questionId.value)
    question.value = res.data
  } catch {
    loadError.value = true
    question.value = null
  } finally {
    loading.value = false
  }
}

// ---------- 编辑 ----------
function startEdit() {
  editing.value = true
}

async function handleSave(payload: QuestionUpdateRequest) {
  saving.value = true
  try {
    await updateQuestion(questionId.value, payload)
    ElMessage.success('保存成功')
    editing.value = false
    // 保存成功后重新获取详情，以服务端持久化内容为准
    await fetchDetail()
  } catch (e) {
    // 后端历史答题保护等业务错误：保留编辑内容，提示原因
    const msg = e instanceof Error ? e.message : '保存失败'
    ElMessage.error(msg)
  } finally {
    saving.value = false
  }
}

// ---------- 发布 / 驳回 ----------
async function handlePublish() {
  if (!question.value) return
  try {
    await ElMessageBox.confirm(
      '发布后该题目将进入正式可组卷题库，确认发布？',
      '发布确认',
      { confirmButtonText: '确认发布', cancelButtonText: '取消', type: 'info' },
    )
  } catch {
    return
  }

  reviewing.value = true
  try {
    await reviewQuestion(questionId.value, { action: 'publish', reason: '' })
    ElMessage.success('发布成功')
    await fetchDetail()
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '发布失败')
  } finally {
    reviewing.value = false
  }
}

async function handleReject() {
  if (!question.value) return
  let reason = ''
  try {
    const res = await ElMessageBox.prompt(
      '驳回后该题不会进入正式可组卷题库。请填写驳回原因（至少 2 个字符）：',
      '驳回确认',
      {
        confirmButtonText: '确认驳回',
        cancelButtonText: '取消',
        inputType: 'textarea',
        inputPlaceholder: '例如：内容不准确',
        inputValidator: (v: string) => {
          if (!v || v.trim().length < 2) return '驳回原因至少 2 个字符'
          return true
        },
      },
    )
    reason = res.value
  } catch {
    return
  }

  reviewing.value = true
  try {
    await reviewQuestion(questionId.value, { action: 'reject', reason: reason.trim() })
    ElMessage.success('已驳回')
    await fetchDetail()
  } catch (e) {
    // 失败保留驳回原因由弹窗重新填写，提示错误
    ElMessage.error(e instanceof Error ? e.message : '驳回失败')
  } finally {
    reviewing.value = false
  }
}

// ---------- 下架 ----------
async function handleDisable() {
  if (!question.value) return
  try {
    await ElMessageBox.confirm(
      '下架后，该题目将不再作为正常可组卷题目使用。系统保留历史记录，是否继续？',
      '下架题目',
      { confirmButtonText: '确认下架', cancelButtonText: '取消', type: 'warning' },
    )
  } catch {
    return
  }

  reviewing.value = true
  try {
    await deleteQuestion(questionId.value)
    ElMessage.success('已下架')
    await fetchDetail()
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '下架失败')
  } finally {
    reviewing.value = false
  }
}

function goBack() {
  if (fromReview.value) {
    router.push('/question-management/review')
  } else {
    router.push('/question-management/questions')
  }
}

onMounted(async () => {
  await Promise.all([loadAll(), fetchDetail()])
})
</script>

<template>
  <div class="page-container">
    <div class="page-header">
      <div>
        <h2>{{ fromReview ? '题目审核详情' : '题目详情' }}</h2>
        <p class="description">题目 #{{ questionId }}</p>
      </div>
      <div class="header-actions">
        <el-button @click="goBack">
          <ArrowLeft :size="16" style="margin-right: 4px;" />
          返回
        </el-button>
      </div>
    </div>

    <!-- 错误 -->
    <div v-if="loadError" class="card">
      <div class="empty-state">
        <p class="title">题目加载失败</p>
        <p class="description">无法获取题目信息，请确认题目是否存在</p>
        <el-button type="primary" @click="fetchDetail">重新加载</el-button>
      </div>
    </div>

    <!-- Loading -->
    <div v-else-if="loading" class="card">
      <div class="card-body">
        <el-skeleton :rows="10" animated />
      </div>
    </div>

    <template v-else-if="question">
      <!-- 编辑模式 -->
      <div v-if="editing" class="card">
        <div class="card-header">编辑题目</div>
        <div class="card-body">
          <QuestionForm
            :question="question"
            :saving="saving"
            @save="handleSave"
            @cancel="editing = false"
          />
          <div class="hint-block">
            说明：若该题目已有答题记录，后端将拒绝修改题干、选项、答案和题型，仅允许修改解析、难度等信息。
          </div>
        </div>
      </div>

      <!-- 非编辑模式：预览 + 操作 -->
      <template v-else>
        <!-- 去重疑点提示（独立信息条，不替代预览） -->
        <div v-if="question.dedup_review_status && question.dedup_review_status !== 'none'" class="card" style="margin-bottom: 16px;">
          <div class="card-body" style="padding: 12px 16px;">
            <div class="dedup-alert" :class="`da-${QUESTION_DEDUP_STATUS_CLASSES[question.dedup_effective_decision || question.dedup_review_status] || 'muted'}`">
              <span :class="['status-badge', `status-badge--${QUESTION_DEDUP_STATUS_CLASSES[question.dedup_effective_decision || question.dedup_review_status] || 'muted'}`]">
                {{ getQuestionDedupStatusLabel(question.dedup_effective_decision || question.dedup_review_status) }}
              </span>
              <template v-if="question.dedup_manual_resolution">
                <span class="dedup-hint">
                  人工裁定：{{ question.dedup_manual_resolution === 'duplicate' ? '确认重复' : '确认不重复' }}
                  <span class="muted-text">（自动判定：{{ getQuestionDedupStatusLabel(question.dedup_review_status) }}）</span>
                </span>
              </template>
              <template v-else-if="question.dedup_review_status === 'uncertain'">
                <span class="dedup-hint">去重结果不确定，请人工检查是否存在重复题</span>
              </template>
              <template v-else-if="question.dedup_review_status === 'duplicate'">
                <span class="dedup-hint">存在疑似重复题，请先对比后再审核</span>
              </template>
              <template v-else>
                <span class="dedup-hint">去重判定：不重复</span>
              </template>
              <el-button text type="primary" size="small" style="margin-left: auto;" @click="router.push(`/question-management/dedup?question_id=${questionId}`)">
                查看相似题
              </el-button>
            </div>
          </div>
        </div>

        <!-- 题目预览 -->
        <div class="card">
          <div class="card-header">
            题目预览
            <span class="header-status">
              当前状态：<QuestionStatusTag :status="question.status" />
            </span>
          </div>
          <div class="card-body">
            <QuestionPreview
              :question="question"
              :bank-name="bankName(question.question_bank_id)"
              :knowledge-names="knowledgeNames"
            />
          </div>
        </div>

        <!-- 操作 -->
        <div class="card" style="margin-top: 16px;">
          <div class="card-header">操作</div>
          <div class="card-body">
            <div class="actions-row">
              <el-button type="primary" @click="startEdit">
                <Edit :size="16" style="margin-right: 4px;" />
                编辑题目
              </el-button>

              <!-- 审核操作：仅待审核 -->
              <template v-if="isPendingReview">
                <el-button
                  type="success"
                  :loading="reviewing"
                  @click="handlePublish"
                >
                  <CheckCircle :size="16" style="margin-right: 4px;" />
                  发布
                </el-button>
                <el-button
                  type="danger"
                  plain
                  :loading="reviewing"
                  @click="handleReject"
                >
                  <XCircle :size="16" style="margin-right: 4px;" />
                  驳回
                </el-button>
              </template>

              <!-- 下架：仅已发布 -->
              <el-button
                v-if="isPublished"
                type="danger"
                plain
                :loading="reviewing"
                @click="handleDisable"
              >
                <Ban :size="16" style="margin-right: 4px;" />
                下架题目
              </el-button>

              <!-- 跳转正式列表 -->
              <el-button @click="router.push('/question-management/questions')">
                <Eye :size="16" style="margin-right: 4px;" />
                查看题目列表
              </el-button>
            </div>

            <div v-if="isRejected" class="hint-block">
              该题目已被驳回，不会进入正式可组卷题库。
            </div>
            <div v-if="isDisabled" class="hint-block">
              该题目已下架，不再作为正常可组卷题目使用。
            </div>
          </div>
        </div>
      </template>
    </template>
  </div>
</template>

<style scoped>
.header-actions {
  display: flex;
  gap: 8px;
}

.header-status {
  margin-left: 12px;
  font-size: 13px;
  color: var(--color-muted-foreground);
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.actions-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.dedup-alert {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: var(--radius-md);
}

.dedup-alert.da-warning {
  background: #FFFBEB;
  border: 1px solid #FCD34D;
}

.dedup-alert.da-error {
  background: #FEF2F2;
  border: 1px solid #FCA5A5;
}

.dedup-alert.da-success {
  background: #ECFDF5;
  border: 1px solid #6EE7B7;
}

.dedup-alert.da-muted {
  background: var(--color-muted);
  border: 1px solid var(--color-border);
}

.dedup-hint {
  font-size: 13px;
  color: var(--color-foreground);
}

.muted-text {
  color: var(--color-muted-foreground);
  font-size: 12px;
}

.hint-block {
  margin-top: 12px;
  padding: 10px 12px;
  background: var(--color-muted);
  border-radius: var(--radius-md);
  font-size: 13px;
  color: var(--color-muted-foreground);
}
</style>
