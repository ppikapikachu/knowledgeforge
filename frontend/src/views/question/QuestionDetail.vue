<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getQuestionDetail } from '@/api/question'
import type { Question } from '@/types/question'
import { ElMessage } from 'element-plus'
import { ArrowLeft, Edit, CheckCircle, XCircle } from 'lucide-vue-next'

const route = useRoute()
const router = useRouter()
const loading = ref(true)
const question = ref<Question | null>(null)

const questionId = computed(() => Number(route.params.id))

async function fetchData() {
  loading.value = true
  try {
    const res = await getQuestionDetail(questionId.value)
    question.value = res.data
  } catch {
    ElMessage.error('获取题目详情失败')
  } finally {
    loading.value = false
  }
}

function getQuestionTypeLabel(type: string) {
  const map: Record<string, string> = {
    SINGLE_CHOICE: '单选题',
    MULTIPLE_CHOICE: '多选题',
    TRUE_FALSE: '判断题',
    SHORT_ANSWER: '简答题',
  }
  return map[type] || type
}

function getQuestionTypeClass(type: string) {
  const map: Record<string, string> = {
    SINGLE_CHOICE: 'info',
    MULTIPLE_CHOICE: 'success',
    TRUE_FALSE: 'warning',
    SHORT_ANSWER: 'muted',
  }
  return map[type] || 'muted'
}

function getDifficultyLabel(difficulty: number) {
  const map: Record<number, string> = { 1: '简单', 2: '中等', 3: '困难' }
  return map[difficulty] || '未知'
}

function getDifficultyClass(difficulty: number) {
  const map: Record<number, string> = { 1: 'easy', 2: 'medium', 3: 'hard' }
  return map[difficulty] || ''
}

function getStatusLabel(status: string) {
  const map: Record<string, string> = { DRAFT: '草稿', PUBLISHED: '已发布', DISABLED: '禁用' }
  return map[status] || status
}

function getStatusClass(status: string) {
  const map: Record<string, string> = { DRAFT: 'muted', PUBLISHED: 'success', DISABLED: 'muted' }
  return map[status] || 'muted'
}

function getSourceLabel(source: string) {
  const map: Record<string, string> = { MANUAL: '手工', IMPORT: '导入', AI: 'AI' }
  return map[source] || source
}

function formatDate(dateStr: string) {
  return new Date(dateStr).toLocaleString('zh-CN')
}

onMounted(fetchData)
</script>

<template>
  <div class="page-container">
    <div class="page-header">
      <div>
        <h2>题目详情</h2>
        <p class="description">查看题目详细信息</p>
      </div>
      <div style="display: flex; gap: 8px;">
        <el-button @click="router.back()">
          <ArrowLeft :size="16" style="margin-right: 4px;" />
          返回
        </el-button>
        <el-button type="primary" @click="router.push(`/questions/${questionId}/edit`)">
          <Edit :size="16" style="margin-right: 4px;" />
          编辑
        </el-button>
      </div>
    </div>

    <div v-if="loading" class="card">
      <div class="card-body">
        <el-skeleton :rows="10" animated />
      </div>
    </div>

    <template v-else-if="question">
      <!-- Question content -->
      <div class="card">
        <div class="card-header">题目内容</div>
        <div class="card-body">
          <div class="question-content">{{ question.content }}</div>
        </div>
      </div>

      <!-- Basic info -->
      <div class="card" style="margin-top: 16px;">
        <div class="card-header">基本信息</div>
        <div class="card-body">
          <el-descriptions :column="2" border>
            <el-descriptions-item label="题型">
              <span :class="['status-badge', `status-badge--${getQuestionTypeClass(question.question_type)}`]">
                {{ getQuestionTypeLabel(question.question_type) }}
              </span>
            </el-descriptions-item>
            <el-descriptions-item label="难度">
              <span :class="['difficulty-badge', `difficulty-badge--${getDifficultyClass(question.difficulty)}`]">
                {{ getDifficultyLabel(question.difficulty) }}
              </span>
            </el-descriptions-item>
            <el-descriptions-item label="状态">
              <span :class="['status-badge', `status-badge--${getStatusClass(question.status)}`]">
                {{ getStatusLabel(question.status) }}
              </span>
            </el-descriptions-item>
            <el-descriptions-item label="来源">
              {{ getSourceLabel(question.source_type) }}
            </el-descriptions-item>
            <el-descriptions-item label="质量评分">
              {{ question.quality_score ?? '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="使用次数">
              {{ question.used_count }}
            </el-descriptions-item>
            <el-descriptions-item label="正确次数">
              {{ question.correct_count }}
            </el-descriptions-item>
            <el-descriptions-item label="创建时间">
              {{ formatDate(question.created_at) }}
            </el-descriptions-item>
            <el-descriptions-item label="更新时间">
              {{ formatDate(question.updated_at) }}
            </el-descriptions-item>
          </el-descriptions>
        </div>
      </div>

      <!-- Options for choice questions -->
      <div
        v-if="question.options && question.options.length > 0"
        class="card"
        style="margin-top: 16px;"
      >
        <div class="card-header">选项</div>
        <div class="card-body">
          <div class="options-list">
            <div
              v-for="option in question.options"
              :key="option.id"
              class="option-item"
              :class="{ correct: option.is_correct === 1 }"
            >
              <div class="option-label">{{ option.option_key }}</div>
              <div class="option-content">{{ option.option_content }}</div>
              <div class="option-status">
                <CheckCircle v-if="option.is_correct === 1" :size="18" style="color: var(--color-success);" />
                <XCircle v-else :size="18" style="color: var(--color-muted-foreground);" />
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Answer -->
      <div class="card" style="margin-top: 16px;">
        <div class="card-header">标准答案</div>
        <div class="card-body">
          <div v-if="question.question_type === 'TRUE_FALSE'" class="answer-text">
            {{ question.answer === 'TRUE' ? '正确' : '错误' }}
          </div>
          <div v-else class="answer-text">{{ question.answer }}</div>
        </div>
      </div>

      <!-- Analysis -->
      <div v-if="question.analysis" class="card" style="margin-top: 16px;">
        <div class="card-header">题目解析</div>
        <div class="card-body">
          <div class="analysis-text">{{ question.analysis }}</div>
        </div>
      </div>

      <!-- Related knowledge -->
      <div v-if="question.knowledge_ids && question.knowledge_ids.length > 0" class="card" style="margin-top: 16px;">
        <div class="card-header">关联知识点</div>
        <div class="card-body">
          <div class="knowledge-tags">
            <el-tag
              v-for="id in question.knowledge_ids"
              :key="id"
              type="primary"
              @click="router.push(`/knowledge/${id}`)"
              style="cursor: pointer;"
            >
              知识点 #{{ id }}
            </el-tag>
          </div>
        </div>
      </div>
    </template>

    <!-- Error -->
    <div v-else class="card">
      <div class="empty-state">
        <p class="title">题目不存在</p>
        <el-button type="primary" @click="router.push('/questions')">返回列表</el-button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.question-content {
  font-size: 16px;
  line-height: 1.8;
  color: var(--color-foreground);
}

.options-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.option-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border-radius: var(--radius-md);
  background: var(--color-muted);
}

.option-item.correct {
  background: #ECFDF5;
  border: 1px solid #059669;
}

.option-label {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--color-card);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 14px;
  color: var(--color-muted-foreground);
  flex-shrink: 0;
}

.option-content {
  flex: 1;
  font-size: 14px;
}

.option-status {
  flex-shrink: 0;
}

.answer-text {
  font-size: 16px;
  font-weight: 500;
  color: var(--color-foreground);
}

.analysis-text {
  font-size: 14px;
  line-height: 1.6;
  color: var(--color-foreground);
  white-space: pre-wrap;
}

.knowledge-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
</style>
