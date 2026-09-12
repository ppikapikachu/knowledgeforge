<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getImportTaskList, createImportTask } from '@/api/importTask'
import type { ImportTask, ImportTaskQueryParams } from '@/types/importTask'
import { ElMessage, ElUpload } from 'element-plus'
import {
  Search,
  RefreshCw,
  Upload,
  Eye,
  Clock,
} from 'lucide-vue-next'
import type { UploadRequestOptions } from 'element-plus'

const router = useRouter()
const loading = ref(true)
const tableData = ref<ImportTask[]>([])
const total = ref(0)
const uploading = ref(false)

const queryParams = ref<ImportTaskQueryParams>({
  page: 1,
  page_size: 20,
  status: undefined,
})

const statusOptions = [
  { label: '待处理', value: 'PENDING' },
  { label: '运行中', value: 'RUNNING' },
  { label: '成功', value: 'SUCCESS' },
  { label: '部分成功', value: 'PARTIAL_SUCCESS' },
  { label: '失败', value: 'FAILED' },
  { label: '已取消', value: 'CANCELLED' },
]

async function fetchData() {
  loading.value = true
  try {
    const res = await getImportTaskList(queryParams.value)
    tableData.value = res.data.items
    total.value = res.data.total
  } catch {
    ElMessage.error('获取导入任务列表失败')
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

async function handleUpload(options: UploadRequestOptions) {
  const file = options.file
  if (!file) return

  // Validate file type
  const allowedTypes = ['.pdf', '.docx', '.txt', '.md']
  const ext = file.name.toLowerCase().slice(file.name.lastIndexOf('.'))
  if (!allowedTypes.includes(ext)) {
    ElMessage.error('仅支持 PDF、DOCX、TXT、MD 格式')
    return
  }

  // Validate file size (50MB)
  if (file.size > 50 * 1024 * 1024) {
    ElMessage.error('文件大小不能超过 50MB')
    return
  }

  uploading.value = true
  try {
    await createImportTask(file)
    ElMessage.success('上传成功，任务已创建')
    // 上传成功后刷新列表，因为后端可能不返回任务对象
    await fetchData()
  } catch {
    // Error handled by interceptor
  } finally {
    uploading.value = false
  }
}

function getStatusLabel(status: string) {
  const map: Record<string, string> = {
    PENDING: '待处理',
    RUNNING: '运行中',
    SUCCESS: '成功',
    PARTIAL_SUCCESS: '部分成功',
    FAILED: '失败',
    CANCELLED: '已取消',
  }
  return map[status] || status
}

function getStatusClass(status: string) {
  const map: Record<string, string> = {
    PENDING: 'muted',
    RUNNING: 'info',
    SUCCESS: 'success',
    PARTIAL_SUCCESS: 'warning',
    FAILED: 'error',
    CANCELLED: 'muted',
  }
  return map[status] || 'muted'
}

function formatFileSize(bytes: number) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
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
        <h2>导入任务</h2>
        <p class="description">管理题库文件导入任务</p>
      </div>
    </div>

    <!-- Upload area -->
    <div class="upload-area card">
      <div class="card-body">
        <el-upload
          :http-request="handleUpload"
          :show-file-list="false"
          accept=".pdf,.docx,.txt,.md"
          :disabled="uploading"
          drag
        >
          <div class="upload-content">
            <Upload :size="48" style="color: var(--color-muted-foreground);" />
            <div class="upload-text">
              <p class="upload-title">拖拽文件到这里</p>
              <p class="upload-desc">或 点击选择文件</p>
              <p class="upload-hint">PDF / DOCX / TXT / MD</p>
            </div>
          </div>
        </el-upload>
      </div>
    </div>

    <!-- Filter toolbar -->
    <div class="filter-toolbar" style="margin-top: 16px;">
      <el-select
        v-model="queryParams.status"
        placeholder="状态"
        clearable
        style="width: 150px;"
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
        <Clock :size="48" />
        <p class="title">暂无导入任务</p>
        <p class="description">还没有导入过题库文件</p>
      </div>
    </div>

    <!-- Table -->
    <div v-else class="card">
      <el-table :data="tableData" style="width: 100%;">
        <el-table-column prop="file_name" label="文件名" min-width="200" show-overflow-tooltip />
        <el-table-column prop="file_type" label="文件类型" width="100" align="center" />
        <el-table-column prop="file_size" label="文件大小" width="100" align="center">
          <template #default="{ row }">
            {{ formatFileSize(row.file_size) }}
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="120" align="center">
          <template #default="{ row }">
            <span :class="['status-badge', `status-badge--${getStatusClass(row.status)}`]">
              {{ getStatusLabel(row.status) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="progress" label="进度" width="120" align="center">
          <template #default="{ row }">
            <el-progress
              :percentage="row.progress"
              :stroke-width="6"
              :show-text="false"
              style="width: 80px;"
            />
            <span style="font-size: 12px; color: var(--color-muted-foreground);">{{ row.progress }}%</span>
          </template>
        </el-table-column>
        <el-table-column prop="current_step" label="当前步骤" width="150" show-overflow-tooltip />
        <el-table-column prop="created_by" label="创建人ID" width="100" align="center" />
        <el-table-column prop="created_at" label="创建时间" width="160" align="center">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right" align="center">
          <template #default="{ row }">
            <el-button text type="primary" size="small" @click="router.push(`/import-tasks/${row.id}`)">
              <Eye :size="14" style="margin-right: 4px;" />
              查看
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
.upload-area {
  margin-bottom: 0;
}

.upload-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  padding: 32px;
}

.upload-text {
  text-align: center;
}

.upload-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--color-foreground);
  margin-bottom: 4px;
}

.upload-desc {
  font-size: 14px;
  color: var(--color-muted-foreground);
  margin-bottom: 8px;
}

.upload-hint {
  font-size: 12px;
  color: var(--color-muted-foreground);
}
</style>
