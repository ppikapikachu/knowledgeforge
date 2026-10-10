<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getImportTaskList, createImportTask, runImportTask } from '@/api/importTask'
import { getKnowledgeBaseList } from '@/api/knowledgeBase'
import type { ImportTask, ImportTaskQueryParams } from '@/types/importTask'
import type { KnowledgeBase } from '@/types/knowledgeBase'
import { getStatusLabel, getStatusClass } from '@/constants/importTask'
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

const kbOptions = ref<KnowledgeBase[]>([])
const selectedKbId = ref<number | undefined>(undefined)

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

async function fetchKbOptions() {
  try {
    const res = await getKnowledgeBaseList({ page: 1, page_size: 100, status: 1 })
    kbOptions.value = res.data.items
  } catch {
    // Silent
  }
}

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

  // Validate knowledge base
  if (!selectedKbId.value) {
    ElMessage.warning('请先选择目标知识库')
    return
  }

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
    const createRes = await createImportTask(file, selectedKbId.value)
    const taskId = createRes.data?.task_id

    if (!taskId || typeof taskId !== 'number') {
      ElMessage.error('创建任务失败：未返回有效任务 ID')
      return
    }

    // 调用正式执行接口
    try {
      await runImportTask(taskId)
      ElMessage.success('任务已提交，正在后台处理中...')
    } catch {
      ElMessage.error(`任务创建成功（ID: ${taskId}）但启动执行失败，请在任务详情中重试`)
    }

    await fetchData()
    // 跳转到任务详情查看进度；携带 started 标记避免重复显示执行按钮
    router.push({ path: `/import-tasks/${taskId}`, query: { started: '1' } })
  } catch {
    // createImportTask 失败，不调用 /run
  } finally {
    uploading.value = false
  }
}

function getKbName(kbId: number): string {
  const kb = kbOptions.value.find((k) => k.id === kbId)
  return kb ? kb.name : `#${kbId}`
}

function formatFileSize(bytes: number) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

function formatDate(dateStr: string) {
  return new Date(dateStr).toLocaleString('zh-CN')
}

onMounted(async () => {
  await fetchKbOptions()
  fetchData()
})
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
        <!-- 知识库选择器 -->
        <div class="upload-kb-select">
          <label class="upload-kb-label">目标知识库 <span class="required-star">*</span></label>
          <el-select
            v-model="selectedKbId"
            placeholder="请选择目标知识库"
            style="width: 280px;"
          >
            <el-option
              v-for="kb in kbOptions"
              :key="kb.id"
              :label="kb.name"
              :value="kb.id"
              :disabled="kb.status === 0"
            />
          </el-select>
          <div v-if="!selectedKbId" class="upload-kb-hint">未选择知识库将无法上传文件</div>
        </div>

        <el-upload
          :http-request="handleUpload"
          :show-file-list="false"
          accept=".pdf,.docx,.txt,.md"
          :disabled="uploading || !selectedKbId"
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
        <el-table-column prop="file_name" label="文件名" min-width="180" show-overflow-tooltip />
        <el-table-column label="知识库" width="120" align="center">
          <template #default="{ row }">
            <span class="kb-tag">{{ getKbName(row.knowledge_base_id) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="file_type" label="类型" width="80" align="center" />
        <el-table-column prop="file_size" label="大小" width="90" align="center">
          <template #default="{ row }">
            {{ formatFileSize(row.file_size) }}
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="110" align="center">
          <template #default="{ row }">
            <span :class="['status-badge', `status-badge--${getStatusClass(row.status)}`]">
              {{ getStatusLabel(row.status) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="progress" label="进度" width="110" align="center">
          <template #default="{ row }">
            <el-progress
              :percentage="row.progress"
              :stroke-width="6"
              :show-text="false"
              style="width: 70px;"
            />
            <span style="font-size: 12px; color: var(--color-muted-foreground);">{{ row.progress }}%</span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="150" align="center">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right" align="center">
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

.upload-kb-select {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 16px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--color-border, #E5E7EB);
}

.upload-kb-label {
  font-size: 14px;
  font-weight: 500;
  color: var(--color-foreground);
}

.required-star {
  color: var(--color-error, #DC2626);
}

.upload-kb-hint {
  font-size: 12px;
  color: var(--color-muted-foreground, #9CA3AF);
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

.kb-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: var(--radius-sm, 4px);
  background: var(--color-muted, #F3F4F6);
  color: var(--color-foreground);
  font-size: 12px;
}
</style>
