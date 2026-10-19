<script setup lang="ts">
/**
 * AI 生成题目
 * 后端契约：POST /api/v1/question-generation/tasks
 * body: { knowledge_id, question_bank_id, question_type, difficulty, count }
 * count 范围 1~50（后端校验），question_type 四种，difficulty 1/2/3。
 * 当前后端一次只接受单一知识点/题型/难度，不做组合生成。
 */
import { ref, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { createGenerationTask } from '@/api/questionGeneration'
import { getQuestionBankList } from '@/api/questionBank'
import { useQuestionLookups } from '@/composables/useQuestionLookups'
import type { QuestionBank } from '@/types/questionManagement'
import type { Knowledge } from '@/types/knowledge'
import { QUESTION_TYPES, DIFFICULTY_LABELS, QUESTION_TYPE_LABELS } from '@/constants/questionManagement'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Sparkles, ArrowLeft, ListChecks } from 'lucide-vue-next'

const router = useRouter()
const { searchKnowledge } = useQuestionLookups()

const banks = ref<QuestionBank[]>([])
const banksLoading = ref(false)

const knowledgeOptions = ref<Knowledge[]>([])
const knowledgeLoading = ref(false)

const submitting = ref(false)

const form = ref({
  question_bank_id: undefined as number | undefined,
  knowledge_id: undefined as number | undefined,
  question_type: 'SINGLE_CHOICE',
  difficulty: 2,
  count: 5,
})

// ---- 题库加载（服务端分页；首屏取 100 条） ----
async function loadBanks() {
  banksLoading.value = true
  try {
    const res = await getQuestionBankList({ page: 1, page_size: 100, status: 1 })
    banks.value = res.data.items
  } catch {
    ElMessage.error('题库列表加载失败')
  } finally {
    banksLoading.value = false
  }
}

// ---- 知识点远程搜索 ----
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

function validate(): string | null {
  const f = form.value
  if (!f.question_bank_id) return '请选择目标题库'
  if (!f.knowledge_id) return '请选择知识点'
  if (!f.question_type) return '请选择题型'
  if (![1, 2, 3].includes(f.difficulty)) return '请选择难度'
  const n = Number(f.count)
  if (!Number.isInteger(n) || n < 1 || n > 50) return '生成数量必须是 1~50 的整数'
  return null
}

async function handleSubmit() {
  const err = validate()
  if (err) {
    ElMessage.warning(err)
    return
  }

  const f = form.value
  const bankName = banks.value.find((b) => b.id === f.question_bank_id)?.name || `#${f.question_bank_id}`
  const knName = knowledgeOptions.value.find((k) => k.id === f.knowledge_id)?.name || `#${f.knowledge_id}`

  try {
    await ElMessageBox.confirm(
      `即将创建 AI 出题任务：\n题库：${bankName}\n知识点：${knName}\n题型：${QUESTION_TYPE_LABELS[f.question_type]}\n难度：${DIFFICULTY_LABELS[f.difficulty]}\n数量：${f.count}`,
      '参数确认',
      { confirmButtonText: '开始生成', cancelButtonText: '返回修改', type: 'info' },
    )
  } catch {
    return
  }

  submitting.value = true
  try {
    const res = await createGenerationTask({
      knowledge_id: f.knowledge_id!,
      question_bank_id: f.question_bank_id!,
      question_type: f.question_type,
      difficulty: f.difficulty,
      count: Number(f.count),
    })
    const taskId = res.data?.task_id
    if (!taskId) {
      ElMessage.error('任务创建结果异常：未返回 task_id，请到任务列表核实')
      return
    }
    ElMessage.success(res.data?.message || '任务已创建')
    router.push(`/question-management/tasks/${taskId}`)
  } catch (e) {
    // 超时无法确认服务器是否已创建：不自动重试 POST
    const msg = e instanceof Error ? e.message : ''
    if (msg.includes('timeout') || msg.includes('超时')) {
      ElMessage.warning('请求超时，任务可能已在后台创建，请先到「生成任务」列表核实，不要重复提交')
    }
    // 其他业务错误已由请求拦截器提示，保留表单内容
  } finally {
    submitting.value = false
  }
}

watch(
  () => form.value.question_type,
  () => {
    // 题型变化不影响其他参数，仅保持表单
  },
)

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
          选择一个题库、一个知识点、一种题型和难度，提交后台生成任务。生成结果需在「题目审核」中人工审核后才会发布。
        </p>
      </div>
      <div class="header-actions">
        <el-button @click="router.push('/question-management/tasks')">
          <ListChecks :size="16" style="margin-right: 4px;" />
          生成任务
        </el-button>
      </div>
    </div>

    <div class="card">
      <div class="card-body">
        <el-form :model="form" label-width="110px" label-position="right" style="max-width: 640px;">
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

          <el-form-item label="知识点" required>
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

          <el-form-item label="生成数量" required>
            <el-input-number v-model="form.count" :min="1" :max="50" :step="1" />
            <div class="field-hint">1 ~ 50，由后端校验</div>
          </el-form-item>

          <el-form-item>
            <el-button type="primary" size="large" :loading="submitting" @click="handleSubmit">
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
  </div>
</template>

<style scoped>
.header-actions {
  display: flex;
  gap: 8px;
}

.field-hint {
  font-size: 12px;
  color: var(--color-muted-foreground, #9CA3AF);
  margin-top: 4px;
}

.option-sub {
  float: right;
  font-size: 12px;
  color: var(--color-muted-foreground);
}
</style>
