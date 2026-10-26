<script setup lang="ts">
/**
 * AI 审核批次列表
 * GET /api/v1/question-reviews/batches?status=&created_by=&page=&page_size=
 */
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { getQuestionReviewBatches } from '@/api/questionReview'
import type { ReviewBatchSummary, ReviewBatchQueryParams } from '@/types/questionReviewBatch'
import {
  getBatchStatusLabel,
  getBatchStatusClass,
  isBatchRunning,
} from '@/constants/questionReviewBatch'
import { formatDateTime } from '@/constants/questionManagement'
import { ElMessage } from 'element-plus'
import { Search, RefreshCw, ClipboardList, Eye, Sparkles } from 'lucide-vue-next'

const router = useRouter()
const loading = ref(true)
const tableData = ref<ReviewBatchSummary[]>([])
const total = ref(0)
const loadError = ref(false)

const queryParams = ref<ReviewBatchQueryParams>({
  page: 1,
  page_size: 20,
  status: undefined,
  created_by: undefined,
})

// 低频自动刷新（存在运行中批次时）
let autoRefreshTimer: ReturnType<typeof setInterval> | null = null
const hasRunning = computed(() => tableData.value.some((b) => isBatchRunning(b.status)))

function startAutoRefresh() {
  stopAutoRefresh()
  autoRefreshTimer = setInterval(() => {
    if (hasRunning.value) {
      fetchData()
    } else {
      stopAutoRefresh()
    }
  }, 5000)
}

function stopAutoRefresh() {
  if (autoRefreshTimer) {
    clearInterval(autoRefreshTimer)
    autoRefreshTimer = null
  }
}

async function fetchData() {
  loading.value = true
  loadError.value = false
  try {
    const params: ReviewBatchQueryParams = { ...queryParams.value }
    if (!params.status) delete params.status
    if (!params.created_by) delete params.created_by

    const res = await getQuestionReviewBatches(params)
    tableData.value = res.data.items
    total.value = res.data.total
  } catch {
    loadError.value = true
    tableData.value = []
  } finally {
    loading.value = false
    if (hasRunning.value) startAutoRefresh()
    else stopAutoRefresh()
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
    status: undefined,
    created_by: undefined,
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

function goToDetail(batchId: number) {
  router.push(`/question-management/review-batches/${batchId}`)
}

onMounted(() => {
  fetchData()
})

onUnmounted(() => {
  stopAutoRefresh()
})
</script>

<template>
  <div class="page-container">
    <div class="page-header">
      <div>
        <h2>AI 审核批次</h2>
        <p class="description">查看手动批量 AI 审核批次的进度与逐题结果</p>
      </div>
      <el-button type="success" @click="router.push('/question-management/review')">
        <Sparkles :size="16" style="margin-right: 4px;" />
        发起批量审核
      </el-button>
    </div>

    <!-- 筛选 -->
    <div class="filter-toolbar">
      <el-select
        v-model="queryParams.status"
        placeholder="批次状态"
        clearable
        style="width: 140px;"
        @change="handleFilterChange"
      >
        <el-option label="排队中" value="queued" />
        <el-option label="审核中" value="running" />
        <el-option label="已完成" value="completed" />
        <el-option label="部分完成" value="partial" />
        <el-option label="执行失败" value="failed" />
        <el-option label="已取消" value="cancelled" />
      </el-select>

      <el-input
        v-model="queryParams.created_by"
        placeholder="创建人 ID"
        clearable
        style="width: 120px;"
        type="number"
        @change="handleFilterChange"
      />

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
        <p class="description">无法获取审核批次列表，请检查后端服务后重试</p>
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
        <ClipboardList :size="48" />
        <p class="title">暂无审核批次</p>
        <p class="description">在题目审核页面选择多道题后，发起 AI 批量审核</p>
      </div>
    </div>

    <!-- 表格 -->
    <div v-else class="card">
      <el-table :data="tableData" style="width: 100%;">
        <el-table-column prop="id" label="批次ID" width="80" align="center" />
        <el-table-column label="状态" width="110" align="center">
          <template #default="{ row }">
            <span :class="['status-badge', `status-badge--${getBatchStatusClass(row.status)}`]">
              {{ getBatchStatusLabel(row.status) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="total_count" label="请求" width="70" align="center" />
        <el-table-column prop="accepted_count" label="接受" width="70" align="center" />
        <el-table-column prop="processed_count" label="已处理" width="80" align="center" />
        <el-table-column prop="auto_approved_count" label="自动通过" width="90" align="center" />
        <el-table-column prop="auto_rejected_count" label="自动驳回" width="90" align="center" />
        <el-table-column prop="manual_review_count" label="转人工" width="80" align="center" />
        <el-table-column prop="failed_count" label="失败" width="70" align="center" />
        <el-table-column prop="skipped_count" label="跳过" width="70" align="center" />
        <el-table-column prop="pending_count" label="待处理" width="80" align="center" />
        <el-table-column prop="created_by" label="创建人" width="80" align="center" />
        <el-table-column label="创建时间" width="150" align="center">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="完成时间" width="150" align="center">
          <template #default="{ row }">{{ formatDateTime(row.finished_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right" align="center">
          <template #default="{ row }">
            <el-button text type="primary" size="small" @click="goToDetail(row.id)">
              <Eye :size="14" style="margin-right: 4px;" />
              查看
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

<style scoped>
.filter-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
</style>
