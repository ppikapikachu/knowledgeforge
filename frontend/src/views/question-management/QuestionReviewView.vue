<script setup lang="ts">
/**
 * 题目审核（待审核列表）
 * GET /api/v1/questions?status=pending_review&question_bank_id=&knowledge_id=
 *   &question_type=&difficulty=&keyword=&page=&page_size=
 * 关键词搜索 300ms 防抖；服务端分页；筛选变更重置页码。
 */
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { getQuestionList } from '@/api/question'
import { useQuestionLookups } from '@/composables/useQuestionLookups'
import type { Question, QuestionQueryParams } from '@/types/question'
import {
  QUESTION_TYPES,
  DIFFICULTIES,
  QUESTION_TYPE_LABELS,
  DIFFICULTY_LABELS,
  DIFFICULTY_CLASSES,
  truncateText,
} from '@/constants/questionManagement'
import QuestionStatusTag from '@/components/question-management/QuestionStatusTag.vue'
import { ElMessage } from 'element-plus'
import { Search, RefreshCw, Inbox, Eye } from 'lucide-vue-next'

const router = useRouter()
const { banks, loadAll, bankName, knowledgeName, searchKnowledge, knowledgeLoading } = useQuestionLookups()

const loading = ref(true)
const tableData = ref<Question[]>([])
const total = ref(0)
const loadError = ref(false)

const knowledgeOptions = ref<{ id: number; name: string }[]>([])

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

onMounted(async () => {
  await Promise.all([loadAll(), fetchData(), handleKnowledgeSearch('')])
})
</script>

<template>
  <div class="page-container">
    <div class="page-header">
      <div>
        <h2>题目审核</h2>
        <p class="description">审核 AI 生成的待审核题目；通过后进入正式可组卷题库，驳回后不进入题库</p>
      </div>
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
      <el-table :data="tableData" style="width: 100%;">
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
  </div>
</template>
