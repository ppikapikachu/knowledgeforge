<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  getKnowledgeBaseList,
  createKnowledgeBase,
  updateKnowledgeBase,
  updateKnowledgeBaseStatus,
} from '@/api/knowledgeBase'
import type {
  KnowledgeBase,
  KnowledgeBaseCreateRequest,
  KnowledgeBaseUpdateRequest,
} from '@/types/knowledgeBase'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Plus,
  Edit,
  Ban,
  CheckCircle,
  BookOpen,
  Database,
} from 'lucide-vue-next'

const router = useRouter()
const loading = ref(true)
const tableData = ref<KnowledgeBase[]>([])
const total = ref(0)

const queryParams = ref({
  page: 1,
  page_size: 20,
  status: undefined as number | undefined,
})

// ---- 创建 / 编辑弹窗 ----
const showDialog = ref(false)
const dialogMode = ref<'create' | 'edit'>('create')
const submitting = ref(false)
const editingId = ref<number | null>(null)

const form = ref<KnowledgeBaseCreateRequest>({
  code: '',
  name: '',
  description: '',
})

const rules = {
  code: [
    { required: true, message: '请输入编码', trigger: 'blur' },
    { max: 50, message: '编码不超过50字符', trigger: 'blur' },
  ],
  name: [
    { required: true, message: '请输入名称', trigger: 'blur' },
    { max: 100, message: '名称不超过100字符', trigger: 'blur' },
  ],
}

const formRef = ref()

async function fetchData() {
  loading.value = true
  try {
    const res = await getKnowledgeBaseList(queryParams.value)
    tableData.value = res.data.items
    total.value = res.data.total
  } catch {
    ElMessage.error('获取知识库列表失败')
  } finally {
    loading.value = false
  }
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

function openCreate() {
  dialogMode.value = 'create'
  editingId.value = null
  form.value = { code: '', name: '', description: '' }
  showDialog.value = true
}

function openEdit(row: KnowledgeBase) {
  dialogMode.value = 'edit'
  editingId.value = row.id
  form.value = {
    code: row.code,
    name: row.name,
    description: row.description || '',
  }
  showDialog.value = true
}

async function handleSubmit() {
  try {
    await formRef.value?.validate()
  } catch {
    return
  }

  submitting.value = true
  try {
    if (dialogMode.value === 'create') {
      await createKnowledgeBase({
        code: form.value.code,
        name: form.value.name,
        description: form.value.description || null,
      })
      ElMessage.success('创建成功')
    } else if (editingId.value) {
      await updateKnowledgeBase(editingId.value, {
        name: form.value.name,
        description: form.value.description || null,
      })
      ElMessage.success('更新成功')
    }
    showDialog.value = false
    fetchData()
  } catch {
    // Error handled by interceptor
  } finally {
    submitting.value = false
  }
}

async function handleToggleStatus(row: KnowledgeBase) {
  const isEnable = row.status === 0
  const actionText = isEnable ? '启用' : '停用'
  try {
    await ElMessageBox.confirm(
      isEnable
        ? `确认启用知识库"${row.name}"？`
        : `确认停用知识库"${row.name}"？停用后不能作为新导入目标。`,
      `${actionText}确认`,
      {
        confirmButtonText: `确认${actionText}`,
        cancelButtonText: '取消',
        type: 'warning',
      },
    )
  } catch {
    return
  }

  try {
    await updateKnowledgeBaseStatus(row.id, { status: isEnable ? 1 : 0 })
    ElMessage.success(`${actionText}成功`)
    fetchData()
  } catch {
    // Error handled by interceptor
  }
}

function enterKnowledgeBase(row: KnowledgeBase) {
  router.push({ path: '/knowledge', query: { kb: row.id } })
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
        <h2>知识库管理</h2>
        <p class="description">管理知识领域，Android、Java、分布式系统等</p>
      </div>
      <el-button type="primary" @click="openCreate">
        <Plus :size="16" style="margin-right: 4px;" />
        新建知识库
      </el-button>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="card">
      <div class="card-body">
        <el-skeleton :rows="8" animated />
      </div>
    </div>

    <!-- Empty -->
    <div v-else-if="tableData.length === 0" class="card">
      <div class="empty-state">
        <Database :size="48" />
        <p class="title">暂无知识库</p>
        <p class="description">创建第一个知识库来组织你的知识点</p>
        <el-button type="primary" @click="openCreate">
          <Plus :size="16" style="margin-right: 4px;" />
          新建知识库
        </el-button>
      </div>
    </div>

    <!-- Cards grid -->
    <template v-else>
      <div class="kb-grid">
        <div
          v-for="kb in tableData"
          :key="kb.id"
          class="kb-card"
          :class="{ disabled: kb.status === 0 }"
          @click="enterKnowledgeBase(kb)"
        >
          <div class="kb-card-header">
            <div class="kb-icon">
              <Database :size="20" />
            </div>
            <div class="kb-meta">
              <div class="kb-name">{{ kb.name }}</div>
              <div class="kb-code">{{ kb.code }}</div>
            </div>
            <span
              :class="['status-badge', kb.status === 1 ? 'status-badge--success' : 'status-badge--muted']"
            >
              {{ kb.status === 1 ? '正常' : '停用' }}
            </span>
          </div>
          <div class="kb-desc">{{ kb.description || '暂无描述' }}</div>
          <div class="kb-footer">
            <div class="kb-count">
              <BookOpen :size="14" />
              <span>{{ kb.knowledge_count }} 个知识点</span>
            </div>
            <div class="kb-actions" @click.stop>
              <el-button text type="primary" size="small" @click="openEdit(kb)">
                <Edit :size="14" style="margin-right: 4px;" />
                编辑
              </el-button>
              <el-button
                v-if="kb.status === 1"
                text
                type="warning"
                size="small"
                @click="handleToggleStatus(kb)"
              >
                <Ban :size="14" style="margin-right: 4px;" />
                停用
              </el-button>
              <el-button
                v-else
                text
                type="success"
                size="small"
                @click="handleToggleStatus(kb)"
              >
                <CheckCircle :size="14" style="margin-right: 4px;" />
                启用
              </el-button>
            </div>
          </div>
          <div class="kb-date">{{ formatDate(kb.updated_at) }}</div>
        </div>
      </div>

      <!-- Pagination -->
      <div class="pagination-wrapper" v-if="total > queryParams.page_size">
        <el-pagination
          v-model:current-page="queryParams.page"
          v-model:page-size="queryParams.page_size"
          :total="total"
          :page-sizes="[12, 24, 48]"
          layout="total, sizes, prev, pager, next"
          @current-change="handlePageChange"
          @size-change="handleSizeChange"
        />
      </div>
    </template>

    <!-- Create / Edit Dialog -->
    <el-dialog
      v-model="showDialog"
      :title="dialogMode === 'create' ? '新建知识库' : '编辑知识库'"
      width="480px"
      :close-on-click-modal="false"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
        <el-form-item label="编码" prop="code">
          <el-input
            v-model="form.code"
            placeholder="如 android、java（创建后不可修改）"
            :disabled="dialogMode === 'edit'"
            maxlength="50"
          />
        </el-form-item>
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" placeholder="如 Android" maxlength="100" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="3"
            placeholder="简短描述该知识库的领域范围"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">
          {{ dialogMode === 'create' ? '创建' : '保存' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.kb-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
}

.kb-card {
  background: var(--color-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: 20px;
  cursor: pointer;
  transition: box-shadow 0.15s ease, border-color 0.15s ease;
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.kb-card:hover {
  box-shadow: var(--shadow-md, 0 4px 12px rgba(0, 0, 0, 0.08));
  border-color: var(--color-primary);
}

.kb-card.disabled {
  opacity: 0.7;
}

.kb-card-header {
  display: flex;
  align-items: center;
  gap: 12px;
}

.kb-icon {
  width: 40px;
  height: 40px;
  border-radius: var(--radius-md);
  background: var(--color-primary-light, #EFF6FF);
  color: var(--color-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.kb-meta {
  flex: 1;
  min-width: 0;
}

.kb-name {
  font-size: 16px;
  font-weight: 600;
  color: var(--color-foreground);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.kb-code {
  font-size: 12px;
  color: var(--color-muted-foreground);
  margin-top: 2px;
}

.kb-desc {
  font-size: 13px;
  color: var(--color-muted-foreground);
  line-height: 1.5;
  min-height: 20px;
}

.kb-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 4px;
}

.kb-count {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  color: var(--color-foreground);
  font-weight: 500;
}

.kb-actions {
  display: flex;
  align-items: center;
  gap: 0;
}

.kb-date {
  font-size: 11px;
  color: var(--color-muted-foreground);
  text-align: right;
}

.pagination-wrapper {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
</style>
