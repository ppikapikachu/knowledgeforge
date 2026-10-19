<script setup lang="ts">
/**
 * 题目编辑表单（审核与题目列表共用）
 *
 * 后端历史答题保护：已有答题记录时 content/answer/options/question_type
 * 不可修改，PUT 会返回业务错误；前端保留用户编辑内容并原样展示后端提示。
 */
import { ref, computed, watch } from 'vue'
import type { Question, QuestionUpdateRequest } from '@/types/question'
import { QUESTION_TYPES, DIFFICULTIES, isChoiceType } from '@/constants/questionManagement'
import { ElMessage } from 'element-plus'
import { Plus, Trash2 } from 'lucide-vue-next'

const props = defineProps<{
  question: Question
  saving?: boolean
}>()

const emit = defineEmits<{
  save: [payload: QuestionUpdateRequest]
  cancel: []
}>()

interface EditOption {
  option_key: string
  option_content: string
  is_correct: number
  sort_order: number
}

const form = ref({
  question_type: '',
  content: '',
  answer: '',
  analysis: '',
  difficulty: 1,
  options: [] as EditOption[],
})

const showOptions = computed(() => isChoiceType(form.value.question_type))

function resetForm() {
  const q = props.question
  form.value = {
    question_type: q.question_type,
    content: q.content,
    answer: q.answer,
    analysis: q.analysis ?? '',
    difficulty: q.difficulty,
    options: (q.options || [])
      .slice()
      .sort((a, b) => a.sort_order - b.sort_order)
      .map((o) => ({
        option_key: o.option_key,
        option_content: o.option_content,
        is_correct: o.is_correct,
        sort_order: o.sort_order,
      })),
  }
}

watch(() => props.question, resetForm, { immediate: true, deep: false })

const trueFalseOptions = [
  { label: '正确', value: 'TRUE' },
  { label: '错误', value: 'FALSE' },
]

function addOption() {
  const idx = form.value.options.length
  form.value.options.push({
    option_key: String.fromCharCode(65 + idx),
    option_content: '',
    is_correct: 0,
    sort_order: idx,
  })
}

function removeOption(index: number) {
  form.value.options.splice(index, 1)
  form.value.options.forEach((opt, i) => {
    opt.option_key = String.fromCharCode(65 + i)
    opt.sort_order = i
  })
}

function setSingleCorrect(index: number) {
  form.value.options.forEach((opt, i) => {
    opt.is_correct = i === index ? 1 : 0
  })
}

function toggleMultiCorrect(index: number) {
  const opt = form.value.options[index]
  if (!opt) return
  opt.is_correct = opt.is_correct === 1 ? 0 : 1
}

function validate(): string | null {
  const f = form.value
  if (!f.content.trim()) return '请填写题目内容'
  if (!f.answer.trim()) return '请填写标准答案'

  if (isChoiceType(f.question_type)) {
    const filled = f.options.filter((o) => o.option_content.trim())
    if (filled.length < 2) return '选项至少需要 2 个'
    const correct = filled.filter((o) => o.is_correct === 1)
    if (f.question_type === 'SINGLE_CHOICE' && correct.length !== 1) {
      return '单选题必须且只能有一个正确答案'
    }
    if (f.question_type === 'MULTIPLE_CHOICE' && correct.length === 0) {
      return '多选题至少需要一个正确答案'
    }
  }

  if (f.question_type === 'TRUE_FALSE' && !['TRUE', 'FALSE'].includes(f.answer)) {
    return '判断题答案必须是 正确(TRUE) 或 错误(FALSE)'
  }

  return null
}

function handleSubmit() {
  const err = validate()
  if (err) {
    ElMessage.warning(err)
    return
  }

  const f = form.value
  const payload: QuestionUpdateRequest = {
    question_type: f.question_type,
    content: f.content,
    answer: f.answer,
    analysis: f.analysis.trim() ? f.analysis : null,
    difficulty: f.difficulty,
  }

  if (isChoiceType(f.question_type)) {
    payload.options = f.options
      .filter((o) => o.option_content.trim())
      .map((o) => ({
        option_key: o.option_key,
        option_content: o.option_content,
        is_correct: o.is_correct,
        sort_order: o.sort_order,
      }))
  }

  emit('save', payload)
}
</script>

<template>
  <div class="q-form">
    <el-form label-width="90px" label-position="right">
      <el-form-item label="题型">
        <el-select v-model="form.question_type" style="width: 200px;">
          <el-option v-for="t in QUESTION_TYPES" :key="t.value" :label="t.label" :value="t.value" />
        </el-select>
      </el-form-item>

      <el-form-item label="题目内容" required>
        <el-input v-model="form.content" type="textarea" :rows="4" placeholder="请输入题目内容" />
      </el-form-item>

      <el-form-item v-if="showOptions" label="选项" required>
        <div class="options-list">
          <div v-for="(opt, idx) in form.options" :key="idx" class="option-row">
            <span class="option-key">{{ opt.option_key }}</span>
            <el-input v-model="opt.option_content" :placeholder="`选项 ${opt.option_key} 内容`" />
            <!-- 单选：设为正确 -->
            <el-button
              v-if="form.question_type === 'SINGLE_CHOICE'"
              :type="opt.is_correct === 1 ? 'success' : 'default'"
              size="small"
              @click="setSingleCorrect(idx)"
            >
              {{ opt.is_correct === 1 ? '正确答案' : '设为正确' }}
            </el-button>
            <!-- 多选：切换正确 -->
            <el-button
              v-else
              :type="opt.is_correct === 1 ? 'success' : 'default'"
              size="small"
              @click="toggleMultiCorrect(idx)"
            >
              {{ opt.is_correct === 1 ? '正确答案' : '设为正确' }}
            </el-button>
            <el-button
              text
              type="danger"
              :disabled="form.options.length <= 2"
              @click="removeOption(idx)"
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

      <el-form-item label="正确答案" required>
        <el-radio-group v-if="form.question_type === 'TRUE_FALSE'" v-model="form.answer">
          <el-radio-button v-for="o in trueFalseOptions" :key="o.value" :value="o.value">
            {{ o.label }}
          </el-radio-button>
        </el-radio-group>
        <el-input v-else v-model="form.answer" type="textarea" :rows="2" placeholder="请输入标准答案" />
      </el-form-item>

      <el-form-item label="解析">
        <el-input v-model="form.analysis" type="textarea" :rows="3" placeholder="解析可为空" />
      </el-form-item>

      <el-form-item label="难度">
        <el-radio-group v-model="form.difficulty">
          <el-radio-button v-for="d in DIFFICULTIES" :key="d.value" :value="d.value">
            {{ d.label }}
          </el-radio-button>
        </el-radio-group>
      </el-form-item>

      <el-form-item>
        <el-button type="primary" :loading="saving" @click="handleSubmit">保存修改</el-button>
        <el-button @click="emit('cancel')">取消</el-button>
      </el-form-item>
    </el-form>
  </div>
</template>

<style scoped>
.options-list {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.option-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.option-key {
  width: 26px;
  height: 26px;
  border-radius: 50%;
  background: var(--color-muted);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 13px;
  flex-shrink: 0;
}
</style>
