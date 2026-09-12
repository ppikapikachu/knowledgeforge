<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { createKnowledgeRelation, getKnowledgeList } from '@/api/knowledge'
import type { KnowledgeRelation, KnowledgeRelationCreateRequest } from '@/types/knowledge'
import type { Knowledge } from '@/types/knowledge'
import { ElMessage, ElDialog, ElForm, ElFormItem, ElSelect, ElOption, ElButton } from 'element-plus'
import { Plus, Trash2, ArrowRight } from 'lucide-vue-next'

const props = defineProps<{
  knowledgeId: number
  relations: KnowledgeRelation[]
}>()

const emit = defineEmits<{
  refresh: []
  delete: [relation: KnowledgeRelation]
}>()

const router = useRouter()
const showDialog = ref(false)
const submitting = ref(false)
const knowledgeOptions = ref<Knowledge[]>([])
const searchLoading = ref(false)

const form = ref<KnowledgeRelationCreateRequest>({
  target_knowledge_id: 0,
  relation_type: 'related',
})

const relationTypes = [
  { label: '前置知识', value: 'prerequisite' },
  { label: '相关知识', value: 'related' },
  { label: '扩展知识', value: 'extension' },
  { label: '对比知识', value: 'contrast' },
]

const relationTypeMap: Record<string, string> = {
  prerequisite: '前置知识',
  related: '相关知识',
  extension: '扩展知识',
  contrast: '对比知识',
}

function groupByType(relations: KnowledgeRelation[]) {
  const groups: Record<string, KnowledgeRelation[]> = {}
  for (const relation of relations) {
    const type = relation.relation_type
    if (!groups[type]) groups[type] = []
    groups[type].push(relation)
  }
  return groups
}

async function handleSearchKnowledge(query: string) {
  if (!query) return
  searchLoading.value = true
  try {
    const res = await getKnowledgeList({ keyword: query, page: 1, page_size: 20 })
    knowledgeOptions.value = res.data.items.filter((k) => k.id !== props.knowledgeId)
  } catch {
    // Silent
  } finally {
    searchLoading.value = false
  }
}

async function handleAddRelation() {
  if (!form.value.target_knowledge_id) {
    ElMessage.warning('请选择目标知识点')
    return
  }
  submitting.value = true
  try {
    await createKnowledgeRelation(props.knowledgeId, form.value)
    ElMessage.success('关系创建成功')
    showDialog.value = false
    form.value = { target_knowledge_id: 0, relation_type: 'related' }
    emit('refresh')
  } catch {
    // Error handled by interceptor
  } finally {
    submitting.value = false
  }
}

function openAddDialog() {
  showDialog.value = true
  form.value = { target_knowledge_id: 0, relation_type: 'related' }
  knowledgeOptions.value = []
}
</script>

<template>
  <div class="relation-container">
    <div class="relation-header">
      <h3>知识关系</h3>
      <el-button type="primary" @click="openAddDialog">
        <Plus :size="16" style="margin-right: 4px;" />
        添加关系
      </el-button>
    </div>

    <div v-if="relations.length === 0" class="empty-state" style="padding: 48px;">
      <ArrowRight :size="48" />
      <p class="title">暂无知识关系</p>
      <p class="description">添加知识点之间的关联关系</p>
      <el-button type="primary" @click="openAddDialog">
        <Plus :size="16" style="margin-right: 4px;" />
        添加关系
      </el-button>
    </div>

    <div v-else class="relation-groups">
      <div
        v-for="(items, type) in groupByType(relations)"
        :key="type"
        class="relation-group"
      >
        <h4 class="group-title">{{ relationTypeMap[type as string] || type }}</h4>
        <div class="group-items">
          <div
            v-for="item in items"
            :key="item.id"
            class="relation-item"
          >
            <div class="relation-info" @click="router.push(`/knowledge/${item.target_knowledge_id}`)">
              <span class="relation-name">{{ item.target_knowledge_name }}</span>
            </div>
            <el-button
              text
              type="danger"
              size="small"
              @click="emit('delete', item)"
            >
              <Trash2 :size="14" />
            </el-button>
          </div>
        </div>
      </div>
    </div>

    <!-- Add Relation Dialog -->
    <el-dialog
      v-model="showDialog"
      title="添加知识关系"
      width="480px"
      :close-on-click-modal="false"
    >
      <el-form :model="form" label-width="100px">
        <el-form-item label="目标知识点" required>
          <el-select
            v-model="form.target_knowledge_id"
            filterable
            remote
            :remote-method="handleSearchKnowledge"
            :loading="searchLoading"
            placeholder="搜索知识点"
            style="width: 100%;"
          >
            <el-option
              v-for="item in knowledgeOptions"
              :key="item.id"
              :label="item.name"
              :value="item.id"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="关系类型" required>
          <el-select v-model="form.relation_type" style="width: 100%;">
            <el-option
              v-for="item in relationTypes"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="showDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleAddRelation">
          确认添加
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.relation-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
}

.relation-header h3 {
  font-size: 16px;
  font-weight: 600;
}

.relation-groups {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.group-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-muted-foreground);
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--color-border);
}

.group-items {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.relation-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: var(--color-muted);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: background 0.15s ease;
}

.relation-item:hover {
  background: var(--color-border);
}

.relation-info {
  flex: 1;
}

.relation-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--color-foreground);
}
</style>
