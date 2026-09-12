<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getKnowledgeList, deleteKnowledge } from '@/api/knowledge'
import type { Knowledge, KnowledgeQueryParams } from '@/types/knowledge'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Plus,
  Search,
  RefreshCw,
  Eye,
  Edit,
  Link,
  Ban,
  BookOpen,
} from 'lucide-vue-next'

const router = useRouter()
const loading = ref(true)
const tableData = ref<Knowledge[]>([])
const total = ref(0)

const queryParams = ref<KnowledgeQueryParams>({
  page: 1,
  page_size: 20,
  keyword: '',
  difficulty: undefined,
  status: undefined,
})

const difficultyOptions = [
  { label: '简单', value: 1 },
  { label: '中等', value: 2 },
  { label: '困难', value: 3 },
]

const statusOptions = [
  { label: '正常', value: 1 },
  { label: '禁用', value: 0 },
]


async function fetchData() {
  loading.value = true
  try {
    const res = await getKnowledgeList(queryParams.value)
    tableData.value = res.data.items
    total.value = res.data.total
  } catch {
    ElMessage.error('获取知识点列表失败')
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
    difficulty: undefined,
    status: undefined,
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

async function handleDelete(row: Knowledge) {
  try {
    await ElMessageBox.confirm(
      `确认删除知识点"${row.name}"？`,
      '删除确认',
      {
        confirmButtonText: '确认删除',
        cancelButtonText: '取消',
        type: 'warning',
      },
    )
    await deleteKnowledge(row.id)
    ElMessage.success('删除成功')
    fetchData()
  } catch {
    // Cancelled
  }
}

function getDifficultyLabel(difficulty: number) {
  const map: Record<number, string> = { 1: '简单', 2: '中等', 3: '困难' }
  return map[difficulty] || '未知'
}

function getDifficultyClass(difficulty: number) {
  const map: Record<number, string> = { 1: 'easy', 2: 'medium', 3: 'hard' }
  return map[difficulty] || ''
}

function getStatusLabel(status: number) {
  return status === 1 ? '正常' : '禁用'
}

function getStatusClass(status: number) {
  return status === 1 ? 'success' : 'muted'
}

function getSourceLabel(source: string) {
  const map: Record<string, string> = { MANUAL: '手工', IMPORT: '导入', AI: 'AI' }
  return map[source] || source
}

function truncateText(text: string | null, maxLen: number) {
  if (!text) return '-'
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
        <h2>知识点管理</h2>
        <p class="description">管理知识库中的所有知识点</p>
      </div>
      <el-button type="primary" @click="router.push('/knowledge/create')">
        <Plus :size="16" style="margin-right: 4px;" />
        新增知识点
      </el-button>
    </div>

    <!-- Filter toolbar -->
    <div class="filter-toolbar">
      <el-input
        v-model="queryParams.keyword"
        placeholder="搜索知识点名称"
        clearable
        style="width: 200px;"
        @keyup.enter="handleSearch"
      >
        <template #prefix>
          <Search :size="16" />
        </template>
      </el-input>

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
        <BookOpen :size="48" />
        <p class="title">暂无知识点</p>
        <p class="description">还没有创建知识点，先创建第一个知识点吧</p>
        <el-button type="primary" @click="router.push('/knowledge/create')">
          <Plus :size="16" style="margin-right: 4px;" />
          创建知识点
        </el-button>
      </div>
    </div>

    <!-- Table -->
    <div v-else class="card">
      <el-table :data="tableData" style="width: 100%;">
        <el-table-column prop="name" label="名称" min-width="180" show-overflow-tooltip />
        <el-table-column prop="summary" label="摘要" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">
            {{ truncateText(row.summary, 50) }}
          </template>
        </el-table-column>
        <el-table-column prop="difficulty" label="难度" width="100" align="center">
          <template #default="{ row }">
            <span :class="['difficulty-badge', `difficulty-badge--${getDifficultyClass(row.difficulty)}`]">
              {{ getDifficultyLabel(row.difficulty) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="source_type" label="来源" width="100" align="center">
          <template #default="{ row }">
            {{ getSourceLabel(row.source_type) }}
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="{ row }">
            <span :class="['status-badge', `status-badge--${getStatusClass(row.status)}`]">
              {{ getStatusLabel(row.status) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="question_count" label="关联题目" width="100" align="center">
          <template #default="{ row }">
            {{ row.question_count ?? 0 }}
          </template>
        </el-table-column>
        <el-table-column prop="updated_at" label="更新时间" width="120" align="center">
          <template #default="{ row }">
            {{ formatDate(row.updated_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right" align="center">
          <template #default="{ row }">
            <el-button text type="primary" size="small" @click="router.push(`/knowledge/${row.id}`)">
              <Eye :size="14" style="margin-right: 4px;" />
              查看
            </el-button>
            <el-button text type="primary" size="small" @click="router.push(`/knowledge/${row.id}/edit`)">
              <Edit :size="14" style="margin-right: 4px;" />
              编辑
            </el-button>
            <el-dropdown trigger="click">
              <el-button text type="primary" size="small">
                更多
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item @click="router.push(`/knowledge/${row.id}?tab=relations`)">
                    <Link :size="14" style="margin-right: 8px;" />
                    关系
                  </el-dropdown-item>
                  <el-dropdown-item @click="handleDelete(row)">
                    <Ban :size="14" style="margin-right: 8px;" />
                    删除
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
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
