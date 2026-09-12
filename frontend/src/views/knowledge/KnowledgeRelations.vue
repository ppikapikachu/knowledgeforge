<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getKnowledgeList } from '@/api/knowledge'
import type { Knowledge } from '@/types/knowledge'
import { ElMessage } from 'element-plus'
import { Search, GitBranch, BookOpen } from 'lucide-vue-next'

const router = useRouter()
const loading = ref(true)
const tableData = ref<Knowledge[]>([])
const total = ref(0)

const queryParams = ref({
  page: 1,
  page_size: 20,
  keyword: '',
})

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

function handlePageChange(page: number) {
  queryParams.value.page = page
  fetchData()
}

function handleSizeChange(size: number) {
  queryParams.value.page_size = size
  queryParams.value.page = 1
  fetchData()
}

onMounted(fetchData)
</script>

<template>
  <div class="page-container">
    <div class="page-header">
      <div>
        <h2>知识关系</h2>
        <p class="description">管理知识点之间的关联关系</p>
      </div>
    </div>

    <!-- Filter toolbar -->
    <div class="filter-toolbar">
      <el-input
        v-model="queryParams.keyword"
        placeholder="搜索知识点名称"
        clearable
        style="width: 240px;"
        @keyup.enter="handleSearch"
      >
        <template #prefix>
          <Search :size="16" />
        </template>
      </el-input>

      <el-button type="primary" @click="handleSearch">
        <Search :size="16" style="margin-right: 4px;" />
        搜索
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
        <GitBranch :size="48" />
        <p class="title">暂无知识点</p>
        <p class="description">请先创建知识点</p>
        <el-button type="primary" @click="router.push('/knowledge/create')">
          创建知识点
        </el-button>
      </div>
    </div>

    <!-- Table -->
    <div v-else class="card">
      <el-table :data="tableData" style="width: 100%;">
        <el-table-column prop="name" label="知识点名称" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">
            <div style="display: flex; align-items: center; gap: 8px;">
              <BookOpen :size="16" style="color: var(--color-primary); flex-shrink: 0;" />
              <span>{{ row.name }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="difficulty" label="难度" width="100" align="center">
          <template #default="{ row }">
            <span :class="['difficulty-badge', `difficulty-badge--${getDifficultyClass(row.difficulty)}`]">
              {{ getDifficultyLabel(row.difficulty) }}
            </span>
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
        <el-table-column prop="updated_at" label="更新时间" width="160" align="center">
          <template #default="{ row }">
            {{ new Date(row.updated_at).toLocaleString('zh-CN') }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right" align="center">
          <template #default="{ row }">
            <el-button
              text
              type="primary"
              size="small"
              @click="router.push(`/knowledge/${row.id}?tab=relations`)"
            >
              <GitBranch :size="14" style="margin-right: 4px;" />
              管理关系
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
