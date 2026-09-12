<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getQuestionDetail, createQuestion, updateQuestion } from '@/api/question'
import { getKnowledgeList } from '@/api/knowledge'
import type { QuestionCreateRequest, QuestionOption } from '@/types/question'
import type { Knowledge } from '@/types/knowledge'
import { ElMessage } from 'element-plus'
import { Save, ArrowLeft, Plus, Trash2 } from 'lucide-vue-next'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const saving = ref(false)

const isEdit = computed(() => !!route.params.id)
const questionId = computed(() => Number(route.params.id))

const form = ref<QuestionCreateRequest>({
  question_type: 'SINGLE_CHOICE',
  content: '',
  answer: '',
  analysis: null,
  difficulty: 1,
  status: 'DRAFT',
  source_type: 'MANUAL',
  quality_score: null,
  options: [
    { option_key: 'A', option_content: '', is_correct: 0, sort_order: 0 },
    { option_key: 'B', option_content: '', is_correct: 0, sort_order: 1 },
    { option_key: 'C', option_content: '', is_correct: 0, sort_order: 2 },
    { option_key: 'D', option_content: '', is_correct: 0, sort_order: 3 },
  ],
  knowledge_ids: null,
})

const knowledgeOptions = ref<Knowledge[]>([])
const knowledgeSearchLoading = ref(false)

const rules = {
  content: [
    { required: true, message: '请输入题目内容', trigger: 'blur' },
  ],
  question_type: [
    { required: true, message: '请选择题型', trigger: 'change' },
  ],
  difficulty: [
    { required: true, message: '请选择难度', trigger: 'change' },
  ],
  answer: [
    { required: true, message: '请输入标准答案', trigger: 'blur' },
  ],
}

const formRef = ref()

const questionTypeOptions = [
  { label: '单选题', value: 'SINGLE_CHOICE' },
  { label: '多选题', value: 'MULTIPLE_CHOICE' },
  { label: '判断题', value: 'TRUE_FALSE' },
  { label: '简答题', value: 'SHORT_ANSWER' },
]

const difficultyOptions = [
  { label: '简单', value: 1 },
  { label: '中等', value: 2 },
  { label: '困难', value: 3 },
]

const statusOptions = [
  { label: '草稿', value: 'DRAFT' },
  { label: '已发布', value: 'PUBLISHED' },
  { label: '禁用', value: 'DISABLED' },
]

const sourceOptions = [
  { label: '手工', value: 'MANUAL' },
  { label: '导入', value: 'IMPORT' },
  { label: 'AI', value: 'AI' },
]

const showOptions = computed(() =>
  ['SINGLE_CHOICE', 'MULTIPLE_CHOICE'].includes(form.value.question_type)
)

const trueFalseOptions = [
  { label: '正确', value: 'TRUE' },
  { label: '错误', value: 'FALSE' },
]

watch(() => form.value.question_type, (type) => {
  if (['SINGLE_CHOICE', 'MULTIPLE_CHOICE'].includes(type)) {
    if (!form.value.options || form.value.options.length === 0) {
      form.value.options = [
        { option_key: 'A', option_content: '', is_correct: 0, sort_order: 0 },
        { option_key: 'B', option_content: '', is_correct: 0, sort_order: 1 },
        { option_key: 'C', option_content: '', is_correct: 0, sort_order: 2 },
        { option_key: 'D', option_content: '', is_correct: 0, sort_order: 3 },
      ]
    }
  } else {
    form.value.options = undefined
  }
  if (type === 'TRUE_FALSE') {
    form.value.answer = 'TRUE'
  } else {
    form.value.answer = ''
  }
})

async function fetchDetail() {
  if (!isEdit.value) return
  loading.value = true
  try {
    const res = await getQuestionDetail(questionId.value)
    const data = res.data
    form.value = {
      question_type: data.question_type,
      content: data.content,
      answer: data.answer,
      analysis: data.analysis,
      difficulty: data.difficulty,
      status: data.status,
      source_type: data.source_type,
      quality_score: data.quality_score ? Number(data.quality_score) : null,
      options: data.options?.length > 0 ? data.options : undefined,
      knowledge_ids: data.knowledge_ids || null,
    }
  } catch {
    ElMessage.error('获取题目详情失败')
  } finally {
    loading.value = false
  }
}

async function handleSearchKnowledge(query: string) {
  if (!query) return
  knowledgeSearchLoading.value = true
  try {
    const res = await getKnowledgeList({ keyword: query, page: 1, page_size: 20 })
    knowledgeOptions.value = res.data.items
  } catch {
    // Silent
  } finally {
    knowledgeSearchLoading.value = false
  }
}

function addOption() {
  if (!form.value.options) form.value.options = []
  const nextKey = String.fromCharCode(65 + form.value.options.length)
  form.value.options.push({
    option_key: nextKey,
    option_content: '',
    is_correct: 0,
    sort_order: form.value.options.length,
  })
}

function removeOption(index: number) {
  form.value.options?.splice(index, 1)
  // Reorder keys
  form.value.options?.forEach((opt, i) => {
    opt.option_key = String.fromCharCode(65 + i)
    opt.sort_order = i
  })
}

function setSingleCorrect(index: number) {
  if (!form.value.options) return
  form.value.options.forEach((opt, i) => {
    opt.is_correct = i === index ? 1 : 0
  })
}

async function handleSubmit() {
  try {
    await formRef.value?.validate()
  } catch {
    return
  }

  // Validate options for choice questions
  if (showOptions.value && form.value.options) {
    const filledOptions = form.value.options.filter((opt) => opt.option_content.trim())
    if (filledOptions.length < 2) {
      ElMessage.warning('至少需要2个选项')
      return
    }
    const correctOptions = filledOptions.filter((opt) => opt.is_correct === 1)
    if (form.value.question_type === 'SINGLE_CHOICE' && correctOptions.length !== 1) {
      ElMessage.warning('单选题必须且只能有一个正确答案')
      return
    }
    if (form.value.question_type === 'MULTIPLE_CHOICE' && correctOptions.length === 0) {
      ElMessage.warning('多选题至少需要一个正确答案')
      return
    }
  }

  if (form.value.question_type === 'TRUE_FALSE' && !form.value.answer) {
    ElMessage.warning('请选择正确答案')
    return
  }

  if (form.value.question_type === 'SHORT_ANSWER' && !form.value.answer?.trim()) {
    ElMessage.warning('请输入标准答案')
    return
  }

  saving.value = true
  try {
    const submitData = { ...form.value }
    // Filter empty options
    if (submitData.options) {
      submitData.options = submitData.options.filter((opt) => opt.option_content.trim())
    }

    if (isEdit.value) {
      await updateQuestion(questionId.value, submitData)
      ElMessage.success('更新成功')
    } else {
      await createQuestion(submitData)
      ElMessage.success('创建成功')
    }
    router.push('/questions')
  } catch {
    // Error handled by interceptor
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  fetchDetail()
  // Load initial knowledge options
  getKnowledgeList({ page: 1, page_size: 50 }).then((res) => {
    knowledgeOptions.value = res.data.items
  }).catch(() => {})
})
</script>

<template>
  <div class="page-container">
    <div class="page-header">
      <div>
        <h2>{{ isEdit ? '编辑题目' : '新增题目' }}</h2>
        <p class="description">{{ isEdit ? '修改题目信息' : '创建新的题目' }}</p>
      </div>
      <el-button @click="router.back()">
        <ArrowLeft :size="16" style="margin-right: 4px;" />
        返回
      </el-button>
    </div>

    <div v-if="loading" class="card">
      <div class="card-body">
        <el-skeleton :rows="10" animated />
      </div>
    </div>

    <div v-else class="card">
      <div class="card-body">
        <el-form
          ref="formRef"
          :model="form"
          :rules="rules"
          label-width="100px"
          label-position="right"
          size="large"
          style="max-width: 800px;"
        >
          <el-form-item label="题型" prop="question_type">
            <el-select v-model="form.question_type" style="width: 200px;">
              <el-option
                v-for="item in questionTypeOptions"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
          </el-form-item>

          <el-form-item label="题目内容" prop="content">
            <el-input
              v-model="form.content"
              type="textarea"
              :rows="4"
              placeholder="请输入题目内容"
            />
          </el-form-item>

          <el-form-item label="难度" prop="difficulty">
            <el-radio-group v-model="form.difficulty">
              <el-radio-button
                v-for="item in difficultyOptions"
                :key="item.value"
                :value="item.value"
              >
                {{ item.label }}
              </el-radio-button>
            </el-radio-group>
          </el-form-item>

          <!-- Options for choice questions -->
          <el-form-item v-if="showOptions" label="选项">
            <div class="options-list">
              <div
                v-for="(option, index) in form.options"
                :key="index"
                class="option-item"
              >
                <div class="option-label">{{ option.option_key }}</div>
                <el-input
                  v-model="option.option_content"
                  :placeholder="`选项 ${option.option_key}`"
                  style="flex: 1;"
                />
                <el-button
                  v-if="form.question_type === 'SINGLE_CHOICE'"
                  :type="option.is_correct === 1 ? 'success' : 'default'"
                  @click="setSingleCorrect(index)"
                >
                  {{ option.is_correct === 1 ? '✓ 正确' : '设为正确' }}
                </el-button>
                <el-checkbox
                  v-else
                  :model-value="option.is_correct === 1"
                  @update:model-value="(val: boolean) => option.is_correct = val ? 1 : 0"
                  label="正确答案"
                />
                <el-button
                  text
                  type="danger"
                  @click="removeOption(index)"
                  :disabled="form.options && form.options.length <= 2"
                >
                  <Trash2 :size="16" />
                </el-button>
              </div>
              <el-button @click="addOption" style="margin-top: 8px;">
                <Plus :size="16" style="margin-right: 4px;" />
                添加选项
              </el-button>
            </div>
          </el-form-item>

          <!-- Correct answer for true/false and short answer -->
          <el-form-item v-if="form.question_type === 'TRUE_FALSE'" label="正确答案" prop="answer">
            <el-radio-group v-model="form.answer">
              <el-radio-button
                v-for="item in trueFalseOptions"
                :key="item.value"
                :value="item.value"
              >
                {{ item.label }}
              </el-radio-button>
            </el-radio-group>
          </el-form-item>

          <el-form-item v-if="form.question_type === 'SHORT_ANSWER'" label="标准答案" prop="answer">
            <el-input
              v-model="form.answer"
              type="textarea"
              :rows="4"
              placeholder="请输入标准答案"
            />
          </el-form-item>

          <el-form-item label="解析">
            <el-input
              v-model="form.analysis"
              type="textarea"
              :rows="3"
              placeholder="请输入题目解析"
            />
          </el-form-item>

          <el-form-item label="关联知识点">
            <el-select
              v-model="form.knowledge_ids"
              multiple
              filterable
              remote
              :remote-method="handleSearchKnowledge"
              :loading="knowledgeSearchLoading"
              placeholder="搜索并选择知识点"
              style="width: 100%;"
            >
              <el-option
                v-for="item in knowledgeOptions"
                :key="item.id"
                :label="item.name"
                :value="item.id"
              />
            </el-select>
          </el-form-item>

          <el-form-item label="状态">
            <el-radio-group v-model="form.status">
              <el-radio-button
                v-for="item in statusOptions"
                :key="item.value"
                :value="item.value"
              >
                {{ item.label }}
              </el-radio-button>
            </el-radio-group>
          </el-form-item>

          <el-form-item label="来源">
            <el-select v-model="form.source_type" style="width: 200px;">
              <el-option
                v-for="item in sourceOptions"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
          </el-form-item>

          <el-form-item>
            <el-button type="primary" :loading="saving" @click="handleSubmit">
              <Save :size="16" style="margin-right: 4px;" />
              {{ isEdit ? '保存修改' : '创建题目' }}
            </el-button>
            <el-button @click="router.back()">取消</el-button>
          </el-form-item>
        </el-form>
      </div>
    </div>
  </div>
</template>

<style scoped>
.options-list {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.option-item {
  display: flex;
  align-items: center;
  gap: 12px;
}

.option-label {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--color-muted);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 14px;
  color: var(--color-muted-foreground);
  flex-shrink: 0;
}
</style>
