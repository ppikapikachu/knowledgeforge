<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { getKnowledgeList, deleteKnowledge } from '@/api/knowledge'
import { getKnowledgeBaseList } from '@/api/knowledgeBase'
import { updateKnowledgeImportance } from '@/api/questionDemand'
import type { Knowledge, KnowledgeQueryParams } from '@/types/knowledge'
import type { KnowledgeBase } from '@/types/knowledgeBase'
import { IMPORTANCE_LEVELS, IMPORTANCE_LABELS, IMPORTANCE_CLASSES, IMPORTANCE_SOURCE_LABELS } from '@/constants/questionDemand'
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
  Star,
} from 'lucide-vue-next'

const router = useRouter()
const route = useRoute()
const loading = ref(true)
const tableData = ref<Knowledge[]>([])
const total = ref(0)

const kbOptions = ref<KnowledgeBase[]>([])

const queryParams = ref<KnowledgeQueryParams>({
  page: 1,
  page_size: 20,
  keyword: '',
  difficulty: undefined,
  status: undefined,
  knowledge_base_id: undefined,
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

// 当前选中的知识库名称
const currentKbName = ref<string>('')

// 重要程度编辑
const importanceDialogVisible = ref(false)
const editingKnowledge = ref<Knowledge | null>(null)
const editingImportanceLevel = ref<string>('normal')
const savingImportance = ref(false)

function openImportanceDialog(row: Knowledge) {
  editingKnowledge.value = row
  editingImportanceLevel.value = row.importance_level || 'normal'
  importanceDialogVisible.value = true
}

async function handleSaveImportance() {
  if (!editingKnowledge.value) return
  savingImportance.value = true
  try {
    await updateKnowledgeImportance(editingKnowledge.value.id, {
      importance_level: editingImportanceLevel.value,
    })
    ElMessage.success('重要程度已更新，来源：管理员调整')
    importanceDialogVisible.value = false
    await fetchData()
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '更新失败')
  } finally {
    savingImportance.value = false
  }
}

async function fetchKbOptions() {
  try {
    const res = await getKnowledgeBaseList({ page: 1, page_size: 100 })
    kbOptions.value = res.data.items
  } catch {
    // Silent
  }
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

function handleKbChange(val: number | undefined) {
  queryParams.value.knowledge_base_id = val
  queryParams.value.page = 1
  updateKbName(val)
  // 更新 URL query
  const query: Record<string, string> = {}
  if (val) query.kb = String(val)
  if (queryParams.value.keyword) query.keyword = queryParams.value.keyword
  router.replace({ path: '/knowledge', query })
  fetchData()
}

function updateKbName(id?: number) {
  if (!id) {
    currentKbName.value = ''
    return
  }
  const kb = kbOptions.value.find((k) => k.id === id)
  currentKbName.value = kb ? kb.name : ''
}

function handleReset() {
  queryParams.value = {
    page: 1,
    page_size: 20,
    keyword: '',
    difficulty: undefined,
    status: undefined,
    knowledge_base_id: undefined,
  }
  currentKbName.value = ''
  router.replace({ path: '/knowledge' })
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

function getKbName(kbId: number): string {
  const kb = kbOptions.value.find((k) => k.id === kbId)
  return kb ? kb.name : `#${kbId}`
}

function truncateText(text: string | null, maxLen: number) {
  if (!text) return '-'
  return text.length > maxLen ? text.slice(0, maxLen) + '...' : text
}

function formatDate(dateStr: string) {
  return new Date(dateStr).toLocaleDateString('zh-CN')
}

onMounted(async () => {
  await fetchKbOptions()
  // 读取 URL 中的 ?kb=xxx
  const kbParam = route.query.kb
  if (kbParam) {
    const kbId = Number(kbParam)
    if (!isNaN(kbId)) {
      queryParams.value.knowledge_base_id = kbId
      updateKbName(kbId)
    }
  }
  fetchData()
})
</script>

<template>
  <div class="page-container">
    <div class="page-header">
      <div>
        <h2>
          知识点管理
          <span v-if="currentKbName" class="kb-breadcrumb">/ {{ currentKbName }}</span>
        </h2>
        <p class="description">
          {{ currentKbName ? `当前知识库：${currentKbName}` : '管理所有知识点' }}
        </p>
      </div>
      <el-button type="primary" @click="router.push('/knowledge/create')">
        <Plus :size="16" style="margin-right: 4px;" />
        新增知识点
      </el-button>
    </div>

    <!-- Filter toolbar -->
    <div class="filter-toolbar">
      <el-select
        v-model="queryParams.knowledge_base_id"
        placeholder="知识库"
        clearable
        style="width: 180px;"
        @change="handleKbChange"
      >
        <el-option
          v-for="kb in kbOptions"
          :key="kb.id"
          :label="kb.name"
          :value="kb.id"
        />
      </el-select>

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
        <p class="description">
          {{ currentKbName ? `知识库"${currentKbName}"还没有知识点` : '还没有创建知识点' }}
        </p>
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
        <el-table-column label="所属知识库" width="130" align="center">
          <template #default="{ row }">
            <span class="kb-tag">{{ getKbName(row.knowledge_base_id) }}</span>
          </template>
        </el-table-column>
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
        <el-table-column prop="source_type" label="来源" width="80" align="center">
          <template #default="{ row }">
            {{ getSourceLabel(row.source_type) }}
          </template>
        </el-table-column>
        <el-table-column label="重要程度" width="110" align="center">
          <template #default="{ row }">
            <span :class="['status-badge', `status-badge--${IMPORTANCE_CLASSES[row.importance_level] || 'muted'}`]">
              {{ IMPORTANCE_LABELS[row.importance_level] || row.importance_level }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="程度来源" width="100" align="center">
          <template #default="{ row }">
            <span class="importance-source-tag">
              {{ IMPORTANCE_SOURCE_LABELS[row.importance_source] || row.importance_source }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="80" align="center">
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
                  <el-dropdown-item @click="openImportanceDialog(row)">
                    <Star :size="14" style="margin-right: 8px;" />
                    修改重要程度
                  </el-dropdown-item>
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
    <!-- 重要程度编辑对话框 -->
    <el-dialog
      v-model="importanceDialogVisible"
      title="修改重要程度"
      width="480px"
      :close-on-click-modal="false"
    >
      <div v-if="editingKnowledge">
        <div class="importance-dialog-header">
          <span class="label">知识点：</span>
          <strong>{{ editingKnowledge.name }}</strong>
        </div>
        <div class="importance-dialog-header">
          <span class="label">当前重要程度：</span>
          <span :class="['status-badge', `status-badge--${IMPORTANCE_CLASSES[editingKnowledge.importance_level] || 'muted'}`]">
            {{ IMPORTANCE_LABELS[editingKnowledge.importance_level] || editingKnowledge.importance_level }}
          </span>
          <span class="importance-source-tag" style="margin-left: 8px;">
            {{ IMPORTANCE_SOURCE_LABELS[editingKnowledge.importance_source] || editingKnowledge.importance_source }}
          </span>
        </div>

        <el-divider />

        <div class="importance-dialog-header">
          <span class="label">目标重要程度：</span>
        </div>
        <el-radio-group v-model="editingImportanceLevel" class="importance-radio-group">
          <el-radio
            v-for="level in IMPORTANCE_LEVELS"
            :key="level.value"
            :value="level.value"
            class="importance-radio"
          >
            <div class="importance-radio-content">
              <div class="importance-radio-title">
                <span :class="['status-badge', `status-badge--${IMPORTANCE_CLASSES[level.value]}`]">
                  {{ level.label }}
                </span>
              </div>
              <div class="importance-radio-desc">{{ level.description }}</div>
            </div>
          </el-radio>
        </el-radio-group>

        <div class="importance-dialog-hint">
          手动设置后，知识导入 Agent 不会覆盖此重要程度（来源将标记为"管理员调整"）。
        </div>
      </div>
      <template #footer>
        <el-button @click="importanceDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingImportance" @click="handleSaveImportance">
          保存修改
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.kb-breadcrumb {
  font-weight: 400;
  color: var(--color-muted-foreground);
  font-size: 14px;
  margin-left: 8px;
}

.kb-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: var(--radius-sm, 4px);
  background: var(--color-muted, #F3F4F6);
  color: var(--color-foreground);
  font-size: 12px;
}

.importance-source-tag {
  display: inline-block;
  padding: 1px 6px;
  border-radius: 3px;
  font-size: 11px;
  background: var(--color-muted);
  color: var(--color-muted-foreground);
}

.importance-dialog-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  font-size: 14px;
}

.importance-dialog-header .label {
  color: var(--color-muted-foreground);
}

.importance-radio-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}

.importance-radio {
  width: 100%;
  height: auto;
  padding: 8px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  margin: 0 !important;
}

.importance-radio.is-checked {
  border-color: var(--color-primary, #1E40AF);
  background: #F0F7FF;
}

.importance-radio-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.importance-radio-title {
  font-weight: 600;
}

.importance-radio-desc {
  font-size: 12px;
  color: var(--color-muted-foreground);
  line-height: 1.4;
}

.importance-dialog-hint {
  margin-top: 16px;
  padding: 10px 12px;
  background: #FFFBEB;
  border-radius: var(--radius-md);
  font-size: 12px;
  color: #92400E;
}
</style>
