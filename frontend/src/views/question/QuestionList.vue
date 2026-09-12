<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getQuestionList, deleteQuestion } from '@/api/question'
import type { Question, QuestionQueryParams } from '@/types/question'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Plus,
  Search,
  RefreshCw,
  Eye,
  Edit,
  FileQuestion,
} from 'lucide-vue-next'

const router = useRouter()
const loading = ref(true)
const tableData = ref<Question[]>([])
const total = ref(0)

const queryParams = ref<QuestionQueryParams>({
  page: 1,
  page_size: 20,
  keyword: '',
  question_type: undefined,
  difficulty: undefined,
  status: undefined,
  source_type: undefined,
})

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

async function fetchData() {
  loading.value = true
  try {
    const res = await getQuestionList(queryParams.value)
    tableData.value = res.data.items
    total.value = res.data.total
  } catch {
    ElMessage.error('获取题目列表失败')
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
    keyword: '',
    question_type: undefined,
    difficulty: undefined,
    status: undefined,
    source_type: undefined,
  }
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

async function handleDelete(row: Question) {
  try {
    await ElMessageBox.confirm(
      `确认删除该题目？`,
      '删除确认',
      {
        confirmButtonText: '确认删除',
        cancelButtonText: '取消',
        type: 'warning',
      },
    )
    await deleteQuestion(row.id)
    ElMessage.success('删除成功')
    fetchData()
  } catch {
    // Cancelled
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

function truncateText(text: string, maxLen: number) {
  return text.length > maxLen ? text.slice(0, maxLen) + '...' : text
}

function formatDate(dateStr: string) {
  return new Date(dateStr).toLocaleDateString('zh-CN')
}

onMounted(fetchData)
</script>

<template>
  <div class="page-container">
    <div class="page-header">
      <div>
        <h2>题目管理</h2>
        <p class="description">管理题库中的所有题目</p>
      </div>
      <el-button type="primary" @click="router.push('/questions/create')">
        <Plus :size="16" style="margin-right: 4px;" />
        新增题目
      </el-button>
    </div>

    <!-- Filter toolbar -->
    <div class="filter-toolbar">
      <el-input
        v-model="queryParams.keyword"
        placeholder="搜索题目内容"
        clearable
        style="width: 200px;"
        @keyup.enter="handleSearch"
      >
        <template #prefix>
          <Search :size="16" />
        </template>
      </el-input>

      <el-select
        v-model="queryParams.question_type"
        placeholder="题型"
        clearable
        style="width: 120px;"
      >
        <el-option
          v-for="item in questionTypeOptions"
          :key="item.value"
          :label="item.label"
          :value="item.value"
        />
      </el-select>

      <el-select
        v-model="queryParams.difficulty"
        placeholder="难度"
        clearable
        style="width: 120px;"
      >
        <el-option
          v-for="item in difficultyOptions"
          :key="item.value"
          :label="item.label"
          :value="item.value"
        />
      </el-select>

      <el-select
        v-model="queryParams.status"
        placeholder="状态"
        clearable
        style="width: 120px;"
      >
        <el-option
          v-for="item in statusOptions"
          :key="item.value"
          :label="item.label"
          :value="item.value"
        />
      </el-select>

      <el-select
        v-model="queryParams.source_type"
        placeholder="来源"
        clearable
        style="width: 120px;"
      >
        <el-option
          v-for="item in sourceOptions"
          :key="item.value"
          :label="item.label"
          :value="item.value"
        />
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

    <!-- Loading -->
    <div v-if="loading" class="card">
      <div class="card-body">
        <el-skeleton :rows="10" animated />
      </div>
    </div>

    <!-- Empty -->
    <div v-else-if="tableData.length === 0" class="card">
      <div class="empty-state">
        <FileQuestion :size="48" />
        <p class="title">暂无题目</p>
        <p class="description">还没有创建题目，先创建第一个题目吧</p>
        <el-button type="primary" @click="router.push('/questions/create')">
          <Plus :size="16" style="margin-right: 4px;" />
          创建题目
        </el-button>
      </div>
    </div>

    <!-- Table -->
    <div v-else class="card">
      <el-table :data="tableData" style="width: 100%;">
        <el-table-column prop="content" label="题目" min-width="250" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="question-content">{{ truncateText(row.content, 60) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="question_type" label="题型" width="100" align="center">
          <template #default="{ row }">
            <span :class="['status-badge', `status-badge--${getQuestionTypeClass(row.question_type)}`]">
              {{ getQuestionTypeLabel(row.question_type) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="difficulty" label="难度" width="100" align="center">
          <template #default="{ row }">
            <span :class="['difficulty-badge', `difficulty-badge--${getDifficultyClass(row.difficulty)}`]">
              {{ getDifficultyLabel(row.difficulty) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="source_type" label="来源" width="80" align="center">
          <template #default="{ row }">
            {{ getSourceLabel(row.source_type) }}
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="80" align="center">
          <template #default="{ row }">
            <span :class="['status-badge', `status-badge--${getStatusClass(row.status)}`]">
              {{ getStatusLabel(row.status) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="quality_score" label="质量" width="80" align="center">
          <template #default="{ row }">
            {{ row.quality_score ?? '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="used_count" label="使用次数" width="100" align="center" />
        <el-table-column prop="updated_at" label="更新时间" width="120" align="center">
          <template #default="{ row }">
            {{ formatDate(row.updated_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right" align="center">
          <template #default="{ row }">
            <el-button text type="primary" size="small" @click="router.push(`/questions/${row.id}`)">
              <Eye :size="14" style="margin-right: 4px;" />
              查看
            </el-button>
            <el-button text type="primary" size="small" @click="router.push(`/questions/${row.id}/edit`)">
              <Edit :size="14" style="margin-right: 4px;" />
              编辑
            </el-button>
            <el-button text type="danger" size="small" @click="handleDelete(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- Pagination -->
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
  </div>
</template>

<style scoped>
.question-content {
  line-height: 1.5;
}
</style>
