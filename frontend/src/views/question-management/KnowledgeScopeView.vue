<script setup lang="ts">
/**
 * 题库知识范围配置
 * GET  /question-banks/{id}/knowledge-bases
 * PUT  /question-banks/{id}/knowledge-bases  (全量替换)
 * GET  /knowledge-bases?page=&page_size=&keyword=
 */
import { ref, onMounted, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  getQuestionBankKnowledgeBases,
  setQuestionBankKnowledgeBases,
} from '@/api/questionDemand'
import { getKnowledgeBaseList } from '@/api/knowledgeBase'
import { getQuestionBankList } from '@/api/questionBank'
import type { QuestionBank } from '@/types/questionManagement'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Save, RefreshCw, Link, ArrowLeft, Database } from 'lucide-vue-next'

const router = useRouter()

const banks = ref<QuestionBank[]>([])
const selectedBankId = ref<number | null>(null)
const loading = ref(false)
const saving = ref(false)

// 可选知识库列表（分页）— status: 1=正常 0=停用（KnowledgeBaseResponse）
const kbItems = ref<Array<{
  id: number
  code: string
  name: string
  description: string | null
  status: number
  knowledge_count: number
}>>([])
const kbTotal = ref(0)
const kbPage = ref(1)
const kbPageSize = ref(50)
const kbKeyword = ref('')
const kbLoading = ref(false)

// 当前已关联
const linkedIds = ref<number[]>([])
const linkedLoading = ref(false)

// 选中集合
const selectedIds = ref<Set<number>>(new Set())

const filteredKbItems = computed(() => {
  return kbItems.value
})

const selectedCount = computed(() => selectedIds.value.size)
const hasChanges = computed(() => {
  const a = new Set(selectedIds.value)
  const b = new Set(linkedIds.value)
  if (a.size !== b.size) return true
  for (const id of a) {
    if (!b.has(id)) return true
  }
  return false
})

async function loadBanks() {
  try {
    const res = await getQuestionBankList({ page: 1, page_size: 100 })
    banks.value = res.data.items
  } catch {
    ElMessage.error('题库列表加载失败')
  }
}

async function loadKnowledgeBases() {
  kbLoading.value = true
  try {
    const res = await getKnowledgeBaseList({
      page: kbPage.value,
      page_size: kbPageSize.value,
      keyword: kbKeyword.value || undefined,
    })
    kbItems.value = res.data.items
    kbTotal.value = res.data.total
  } catch {
    ElMessage.error('知识库列表加载失败')
  } finally {
    kbLoading.value = false
  }
}

async function loadCurrentMapping() {
  if (!selectedBankId.value) {
    linkedIds.value = []
    selectedIds.value = new Set()
    return
  }
  linkedLoading.value = true
  try {
    const res = await getQuestionBankKnowledgeBases(selectedBankId.value)
    linkedIds.value = res.data.knowledge_base_ids
    selectedIds.value = new Set(res.data.knowledge_base_ids)
  } catch {
    ElMessage.error('当前映射加载失败')
  } finally {
    linkedLoading.value = false
  }
}

function handleBankChange() {
  loadCurrentMapping()
}

function toggleSelect(id: number) {
  if (selectedIds.value.has(id)) {
    selectedIds.value.delete(id)
  } else {
    selectedIds.value.add(id)
  }
  selectedIds.value = new Set(selectedIds.value)
}

function handleSearchKb() {
  kbPage.value = 1
  loadKnowledgeBases()
}

async function handleSave() {
  if (!selectedBankId.value) return

  const count = selectedCount.value
  const isClearing = count === 0

  try {
    await ElMessageBox.confirm(
      isClearing
        ? '确认清空该题库的所有知识库关联？清空后智能分配模式不可用。'
        : `确认保存？本操作将全量替换，以当前选择的 ${count} 个知识库覆盖旧关联。`,
      '确认保存',
      {
        confirmButtonText: '确认保存',
        cancelButtonText: '取消',
        type: isClearing ? 'warning' : 'info',
      },
    )
  } catch {
    return
  }

  saving.value = true
  try {
    const ids = Array.from(selectedIds.value)
    await setQuestionBankKnowledgeBases(selectedBankId.value, { knowledge_base_ids: ids })
    ElMessage.success('保存成功')
    await loadCurrentMapping()
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '保存失败')
  } finally {
    saving.value = false
  }
}

function handleReset() {
  selectedIds.value = new Set(linkedIds.value)
}

onMounted(async () => {
  await Promise.all([loadBanks(), loadKnowledgeBases()])
})
</script>

<template>
  <div class="page-container">
    <div class="page-header">
      <div>
        <h2>题库知识范围</h2>
        <p class="description">配置每个题库允许使用哪些知识库，为智能出题确定候选知识点范围</p>
      </div>
      <el-button @click="router.back()">
        <ArrowLeft :size="16" style="margin-right: 4px;" />
        返回
      </el-button>
    </div>

    <!-- 题库选择 -->
    <div class="filter-toolbar">
      <span class="scope-label">选择题库：</span>
      <el-select
        v-model="selectedBankId"
        placeholder="请选择题库"
        style="width: 240px;"
        @change="handleBankChange"
      >
        <el-option
          v-for="b in banks"
          :key="b.id"
          :label="b.name"
          :value="b.id"
        />
      </el-select>
      <el-button @click="loadCurrentMapping">
        <RefreshCw :size="16" style="margin-right: 4px;" />
        刷新
      </el-button>
    </div>

    <!-- 无题库时 -->
    <div v-if="!selectedBankId" class="card">
      <div class="empty-state">
        <Link :size="48" />
        <p class="title">请选择题库</p>
        <p class="description">选择题库后，配置其关联的知识库范围</p>
      </div>
    </div>

    <template v-else>
      <!-- 当前关联状态 -->
      <div class="card">
        <div class="card-body">
          <div class="link-status">
            <Link :size="18" />
            <div>
              <div class="link-title">
                当前已关联 <strong>{{ linkedIds.length }}</strong> 个知识库
                <template v-if="hasChanges">
                  <span class="changed-hint">（已修改，未保存）</span>
                </template>
              </div>
              <div class="link-desc">
                智能分配只能从此题库关联的知识库中选择知识点。修改后请保存生效。
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 知识库列表 -->
      <div class="card" style="margin-top: 16px;">
        <div class="card-header">
          选择关联知识库
          <div class="kb-search">
            <el-input
              v-model="kbKeyword"
              placeholder="搜索知识库"
              clearable
              style="width: 200px;"
              @keyup.enter="handleSearchKb"
              @clear="handleSearchKb"
            />
            <el-button size="small" @click="handleSearchKb">搜索</el-button>
          </div>
        </div>
        <div class="card-body">
          <div v-if="kbLoading" class="kb-loading">
            <el-skeleton :rows="3" animated />
          </div>
          <div v-else-if="filteredKbItems.length === 0" class="kb-empty">
            没有可选的知识库
          </div>
          <div v-else class="kb-grid">
            <div
              v-for="kb in filteredKbItems"
              :key="kb.id"
              class="kb-item"
              :class="{ selected: selectedIds.has(kb.id) }"
              @click="toggleSelect(kb.id)"
            >
              <div class="kb-check">
                <span v-if="selectedIds.has(kb.id)" class="check-icon">✓</span>
              </div>
              <div class="kb-info">
                <div class="kb-name">{{ kb.name }}</div>
                <div class="kb-desc">{{ kb.description || '暂无描述' }}</div>
                <div class="kb-meta">
                  <Database :size="12" />
                  <span>{{ kb.knowledge_count }} 个知识点</span>
                  <span class="kb-status" :class="kb.status === 1 ? 'active' : 'disabled'">
                    {{ kb.status === 1 ? '启用' : '停用' }}
                  </span>
                </div>
              </div>
            </div>
          </div>

          <!-- 分页 -->
          <div class="pagination-wrapper" v-if="kbTotal > kbPageSize">
            <el-pagination
              v-model:current-page="kbPage"
              :page-size="kbPageSize"
              :total="kbTotal"
              layout="prev, pager, next"
              @current-change="loadKnowledgeBases"
            />
          </div>
        </div>
      </div>

      <!-- 操作 -->
      <div class="card" style="margin-top: 16px;">
        <div class="card-body">
          <div class="actions-row">
            <el-button type="primary" :loading="saving" :disabled="!hasChanges" @click="handleSave">
              <Save :size="16" style="margin-right: 4px;" />
              保存关联（{{ selectedCount }} 个）
            </el-button>
            <el-button @click="handleReset" :disabled="!hasChanges">
              撤销修改
            </el-button>
          </div>
          <div class="save-hint">
            保存为全量替换操作：将以当前选中的 {{ selectedCount }} 个知识库覆盖旧关联。
            清空所有选中后保存表示解除全部关联。
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.scope-label {
  font-size: 14px;
  color: var(--color-muted-foreground);
  margin-right: 8px;
}

.link-status {
  display: flex;
  gap: 10px;
  align-items: flex-start;
}

.link-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-foreground);
}

.changed-hint {
  font-size: 12px;
  color: var(--color-warning, #D97706);
  font-weight: 400;
}

.link-desc {
  font-size: 13px;
  color: var(--color-muted-foreground);
  margin-top: 4px;
}

.kb-search {
  display: flex;
  gap: 8px;
  margin-left: 12px;
}

.kb-loading,
.kb-empty {
  padding: 24px;
  text-align: center;
  color: var(--color-muted-foreground);
}

.kb-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 12px;
}

.kb-item {
  display: flex;
  gap: 12px;
  padding: 14px;
  border: 2px solid var(--color-border);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all 0.15s ease;
}

.kb-item:hover {
  border-color: var(--color-primary, #1E40AF);
  background: #F8FAFF;
}

.kb-item.selected {
  border-color: var(--color-primary, #1E40AF);
  background: #EFF6FF;
}

.kb-check {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  border: 2px solid var(--color-border);
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-top: 2px;
}

.kb-item.selected .kb-check {
  background: var(--color-primary, #1E40AF);
  border-color: var(--color-primary, #1E40AF);
}

.check-icon {
  color: #fff;
  font-size: 12px;
  font-weight: 700;
}

.kb-info {
  flex: 1;
  min-width: 0;
}

.kb-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-foreground);
}

.kb-desc {
  font-size: 12px;
  color: var(--color-muted-foreground);
  margin-top: 4px;
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.kb-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 8px;
  font-size: 12px;
  color: var(--color-muted-foreground);
}

.kb-status {
  margin-left: auto;
  padding: 1px 6px;
  border-radius: 3px;
  font-size: 11px;
}

.kb-status.active {
  background: #ECFDF5;
  color: #059669;
}

.kb-status.disabled {
  background: var(--color-muted);
  color: var(--color-muted-foreground);
}

.actions-row {
  display: flex;
  gap: 8px;
}

.save-hint {
  margin-top: 12px;
  font-size: 12px;
  color: var(--color-muted-foreground);
}
</style>
