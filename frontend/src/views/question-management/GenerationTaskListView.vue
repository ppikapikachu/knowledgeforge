<script setup lang="ts">
/**
 * 生成任务列表
 * GET /api/v1/question-generation/tasks?page=&page_size=&status=
 * 列表项真实字段：id, status, total_count, success_count, duplicate_count,
 * failed_count, request_config, error_summary, started_at, completed_at, created_at
 * 题库/知识点名称由 request_config 中的 id 经真实题库/知识点接口映射，不伪造。
 */
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { getGenerationTaskList } from '@/api/questionGeneration'
import { useQuestionLookups } from '@/composables/useQuestionLookups'
import type { GenerationTask } from '@/types/questionManagement'
import {
  TASK_STATUSES,
  QUESTION_TYPE_LABELS,
  DIFFICULTY_LABELS,
  formatDateTime,
} from '@/constants/questionManagement'
import { ALLOCATION_MODE_LABELS } from '@/constants/questionDemand'
import TaskStatusTag from '@/components/question-management/TaskStatusTag.vue'
import { ElMessage } from 'element-plus'
import { Search, RefreshCw, Eye, Sparkles, ClipboardList } from 'lucide-vue-next'

const router = useRouter()
const { loadAll, bankName, knowledgeName } = useQuestionLookups()

const loading = ref(true)
const tableData = ref<GenerationTask[]>([])
const total = ref(0)
const loadError = ref(false)

const queryParams = ref({
  page: 1,
  page_size: 20,
  status: '' as string,
})

function configOf(task: GenerationTask): Record<string, unknown> {
  return task.request_config || {}
}

function cfgNumber(cfg: Record<string, unknown>, key: string): number | undefined {
  const v = cfg[key]
  return typeof v === 'number' ? v : undefined
}

function bankLabel(task: GenerationTask): string {
  const id = cfgNumber(configOf(task), 'question_bank_id')
  return id ? bankName(id) : '-'
}

function knowledgeLabel(task: GenerationTask): string {
  const id = cfgNumber(configOf(task), 'knowledge_id')
  return id ? knowledgeName(id) : '-'
}

function typeLabel(task: GenerationTask): string {
  const t = configOf(task).question_type
  return typeof t === 'string' ? QUESTION_TYPE_LABELS[t] || t : '-'
}

function difficultyLabel(task: GenerationTask): string {
  const d = cfgNumber(configOf(task), 'difficulty')
  return d ? DIFFICULTY_LABELS[d] || String(d) : '-'
}

const hasFilters = computed(() => !!queryParams.value.status)

async function fetchData() {
  loading.value = true
  loadError.value = false
  try {
    const res = await getGenerationTaskList({
      page: queryParams.value.page,
      page_size: queryParams.value.page_size,
      status: queryParams.value.status || undefined,
    })
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
  queryParams.value = { page: 1, page_size: 20, status: '' }
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

onMounted(async () => {
  await Promise.all([loadAll(), fetchData()])
})
</script>

<template>
  <div class="page-container">
    <div class="page-header">
      <div>
        <h2>生成任务</h2>
        <p class="description">查看 AI 出题任务的执行状态与结果</p>
      </div>
      <el-button type="primary" @click="router.push('/question-management/generate')">
        <Sparkles :size="16" style="margin-right: 4px;" />
        AI 生成题目
      </el-button>
    </div>

    <!-- 筛选 -->
    <div class="filter-toolbar">
      <el-select v-model="queryParams.status" placeholder="任务状态" clearable style="width: 160px;">
        <el-option v-for="s in TASK_STATUSES" :key="s.value" :label="s.label" :value="s.value" />
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

    <!-- 错误状态 -->
    <div v-if="loadError" class="card">
      <div class="empty-state">
        <p class="title">任务列表加载失败</p>
        <p class="description">请检查后端服务或网络连接后重试</p>
        <el-button type="primary" @click="fetchData">重新加载</el-button>
      </div>
    </div>

    <!-- Loading -->
    <div v-else-if="loading" class="card">
      <div class="card-body">
        <el-skeleton :rows="8" animated />
      </div>
    </div>

    <!-- 空状态 -->
    <div v-else-if="tableData.length === 0" class="card">
      <div class="empty-state">
        <ClipboardList :size="48" />
        <p class="title">{{ hasFilters ? '没有符合条件的任务' : '暂无生成任务' }}</p>
        <p class="description">
          {{ hasFilters ? '请调整筛选条件后重试' : '创建第一个 AI 出题任务，生成的题目需审核后才会发布' }}
        </p>
        <el-button v-if="!hasFilters" type="primary" @click="router.push('/question-management/generate')">
          <Sparkles :size="16" style="margin-right: 4px;" />
          AI 生成题目
        </el-button>
      </div>
    </div>

    <!-- 表格 -->
    <div v-else class="card">
      <el-table :data="tableData" style="width: 100%;">
        <el-table-column prop="id" label="任务ID" width="80" align="center" />
        <el-table-column label="分配模式" width="110" align="center">
          <template #default="{ row }">
            <span v-if="row.allocation_mode" class="mode-tag">
              {{ ALLOCATION_MODE_LABELS[row.allocation_mode] || row.allocation_mode }}
            </span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="题库" width="130" align="center">
          <template #default="{ row }">{{ bankLabel(row) }}</template>
        </el-table-column>
        <el-table-column label="知识点" width="150" show-overflow-tooltip>
          <template #default="{ row }">{{ knowledgeLabel(row) }}</template>
        </el-table-column>
        <el-table-column label="题型" width="100" align="center">
          <template #default="{ row }">{{ typeLabel(row) }}</template>
        </el-table-column>
        <el-table-column label="难度" width="80" align="center">
          <template #default="{ row }">{{ difficultyLabel(row) }}</template>
        </el-table-column>
        <el-table-column prop="total_count" label="计划" width="70" align="center" />
        <el-table-column label="分配(请求/可分配/未分配)" width="170" align="center">
          <template #default="{ row }">
            <template v-if="row.requested_count !== null">
              {{ row.requested_count }} / {{ row.allocated_count }} / {{ row.unallocated_count }}
            </template>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="生成/判重/失败" width="120" align="center">
          <template #default="{ row }">
            {{ row.generated_count }} / {{ row.duplicate_count }} / {{ row.failed_count }}
          </template>
        </el-table-column>
        <el-table-column label="待复核" width="90" align="center">
          <template #default="{ row }">
            <span
              v-if="row.uncertain_count > 0"
              class="status-badge status-badge--warning"
              style="cursor: pointer;"
              @click="router.push(`/question-management/dedup?task_id=${row.id}&needs_manual_review=1`)"
            >
              {{ row.uncertain_count }} 条
            </span>
            <span v-else class="muted-text">0</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="110" align="center">
          <template #default="{ row }">
            <TaskStatusTag :status="row.status" />
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="160" align="center">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="完成时间" width="160" align="center">
          <template #default="{ row }">{{ formatDateTime(row.completed_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right" align="center">
          <template #default="{ row }">
            <el-button text type="primary" size="small" @click="router.push(`/question-management/tasks/${row.id}`)">
              <Eye :size="14" style="margin-right: 4px;" />
              查看
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
.mode-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  background: #EFF6FF;
  color: var(--color-primary, #1E40AF);
}

.muted-text {
  color: var(--color-muted-foreground);
  font-size: 12px;
}
</style>
