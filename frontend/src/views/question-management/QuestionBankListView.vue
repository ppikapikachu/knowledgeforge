<script setup lang="ts">
/**
 * 题库管理列表（含练习开放开关）
 * GET  /api/v1/question-banks
 * PATCH /api/v1/question-banks/{id}/practice-availability
 */
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { getQuestionBankList, updateQuestionBankPracticeAvailability } from '@/api/questionBank'
import type { QuestionBank, QuestionBankQueryParams } from '@/types/questionManagement'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, RefreshCw, Settings, Link, BookOpen } from 'lucide-vue-next'

const router = useRouter()
const loading = ref(true)
const tableData = ref<QuestionBank[]>([])
const total = ref(0)
const loadError = ref(false)

const queryParams = ref<QuestionBankQueryParams>({
  page: 1,
  page_size: 20,
  keyword: '',
  status: undefined,
})

// 每行开关 loading 锁（防止重复提交）
const togglingIds = ref<Set<number>>(new Set())

function isToggling(id: number): boolean {
  return togglingIds.value.has(id)
}

async function fetchData() {
  loading.value = true
  loadError.value = false
  try {
    const params: QuestionBankQueryParams = { ...queryParams.value }
    if (!params.keyword) delete params.keyword
    if (params.status === undefined || params.status === null) delete params.status

    const res = await getQuestionBankList(params)
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
    keyword: '',
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

async function handleTogglePractice(row: QuestionBank) {
  const target = !row.is_available_for_practice
  const confirmText = target
    ? '开放后，普通用户可以在练习选题库页面看到该题库，并使用其中已发布的题目组卷。是否继续？'
    : '关闭后，普通用户不能再使用该题库创建新的试卷。已经生成的历史试卷和练习记录不会删除，用户仍可继续历史未完成会话及回顾已完成试卷。是否继续？'

  try {
    await ElMessageBox.confirm(confirmText, target ? '开放练习' : '关闭练习', {
      confirmButtonText: target ? '确认开放' : '确认关闭',
      cancelButtonText: '取消',
      type: target ? 'info' : 'warning',
    })
  } catch {
    return
  }

  togglingIds.value.add(row.id)
  try {
    const res = await updateQuestionBankPracticeAvailability(row.id, {
      is_available_for_practice: target,
    })
    // 用服务端响应更新当前行（统计可能随之变化）
    const updated = res.data
    const idx = tableData.value.findIndex((b) => b.id === row.id)
    if (idx !== -1) {
      tableData.value[idx] = { ...tableData.value[idx], ...updated }
    }
    ElMessage.success(target ? '已开放练习' : '已关闭练习')
  } catch (e) {
    // 请求失败保留原状态，展示后端错误
    ElMessage.error(e instanceof Error ? e.message : '操作失败')
  } finally {
    togglingIds.value.delete(row.id)
  }
}

onMounted(fetchData)
</script>

<template>
  <div class="page-container">
    <div class="page-header">
      <div>
        <h2>题库管理</h2>
        <p class="description">管理题库信息，控制是否开放给普通用户练习</p>
      </div>
    </div>

    <!-- 筛选 -->
    <div class="filter-toolbar">
      <el-input
        v-model="queryParams.keyword"
        placeholder="搜索题库名称"
        clearable
        style="width: 200px;"
        @keyup.enter="handleSearch"
      >
        <template #prefix><Search :size="16" /></template>
      </el-input>

      <el-select
        v-model="queryParams.status"
        placeholder="状态"
        clearable
        style="width: 120px;"
        @change="handleSearch"
      >
        <el-option label="启用" :value="1" />
        <el-option label="停用" :value="0" />
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
        <p class="description">无法获取题库列表，请检查后端服务后重试</p>
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
        <BookOpen :size="48" />
        <p class="title">暂无题库</p>
        <p class="description">创建题库后可在此管理练习开放设置</p>
      </div>
    </div>

    <!-- 表格 -->
    <div v-else class="card">
      <el-table :data="tableData" style="width: 100%;">
        <el-table-column prop="name" label="题库名称" min-width="150" show-overflow-tooltip />
        <el-table-column prop="description" label="描述" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.description || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="已发布题目" width="100" align="center">
          <template #default="{ row }">
            <strong>{{ row.published_question_count }}</strong>
          </template>
        </el-table-column>
        <el-table-column label="待审核题目" width="100" align="center">
          <template #default="{ row }">
            <span :class="row.pending_review_count > 0 ? 'warn-text' : 'muted-text'">
              {{ row.pending_review_count }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="组卷条件" width="110" align="center">
          <template #default="{ row }">
            <span v-if="row.can_assemble" class="status-badge status-badge--success">可组卷</span>
            <span v-else class="status-badge status-badge--muted">暂无可用题目</span>
          </template>
        </el-table-column>
        <el-table-column label="用户练习权限" width="130" align="center">
          <template #default="{ row }">
            <div class="practice-toggle">
              <el-switch
                :model-value="row.is_available_for_practice"
                :loading="isToggling(row.id)"
                :disabled="isToggling(row.id)"
                @change="() => handleTogglePractice(row)"
              />
              <span class="practice-label" :class="row.is_available_for_practice ? 'opened' : 'closed'">
                {{ row.is_available_for_practice ? '已开放' : '未开放' }}
              </span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" align="center">
          <template #default="{ row }">
            <el-button text type="primary" size="small" @click="router.push(`/question-management/knowledge-scope?qb_id=${row.id}`)">
              <Link :size="14" style="margin-right: 4px;" />
              知识范围
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
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
.filter-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.practice-toggle {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.practice-label {
  font-size: 12px;
}

.practice-label.opened {
  color: var(--color-success, #059669);
}

.practice-label.closed {
  color: var(--color-muted-foreground);
}

.warn-text {
  color: var(--color-warning, #D97706);
  font-weight: 600;
}

.muted-text {
  color: var(--color-muted-foreground);
}
</style>
