<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getKnowledgeDetail, getKnowledgeRelations, deleteKnowledgeRelation } from '@/api/knowledge'
import { getKnowledgeBaseDetail } from '@/api/knowledgeBase'
import type { Knowledge, KnowledgeRelation } from '@/types/knowledge'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, Edit, Trash2 } from 'lucide-vue-next'
import KnowledgeRelationList from '@/components/knowledge/KnowledgeRelationList.vue'

const route = useRoute()
const router = useRouter()
const loading = ref(true)
const knowledge = ref<Knowledge | null>(null)
const relations = ref<KnowledgeRelation[]>([])
const activeTab = ref(route.query.tab === 'relations' ? 'relations' : 'info')
const kbName = ref('')

const knowledgeId = computed(() => Number(route.params.id))

async function fetchData() {
  loading.value = true
  try {
    const [detailRes, relationsRes] = await Promise.all([
      getKnowledgeDetail(knowledgeId.value),
      getKnowledgeRelations(knowledgeId.value),
    ])
    knowledge.value = detailRes.data
    relations.value = relationsRes.data

    // 加载知识库名称
    if (knowledge.value?.knowledge_base_id) {
      try {
        const kbRes = await getKnowledgeBaseDetail(knowledge.value.knowledge_base_id)
        kbName.value = kbRes.data.name
      } catch {
        kbName.value = ''
      }
    }
  } catch {
    ElMessage.error('获取知识点详情失败')
  } finally {
    loading.value = false
  }
}

async function handleDeleteRelation(relation: KnowledgeRelation) {
  try {
    await ElMessageBox.confirm(
      `确认删除该知识关系？`,
      '删除确认',
      {
        confirmButtonText: '确认删除',
        cancelButtonText: '取消',
        type: 'warning',
      },
    )
    await deleteKnowledgeRelation(knowledgeId.value, relation.id)
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

function formatDate(dateStr: string) {
  return new Date(dateStr).toLocaleString('zh-CN')
}

onMounted(fetchData)
</script>

<template>
  <div class="page-container">
    <div class="page-header">
      <div>
        <h2>知识点详情</h2>
        <p class="description">查看知识点详细信息和关联关系</p>
      </div>
      <div style="display: flex; gap: 8px;">
        <el-button @click="router.back()">
          <ArrowLeft :size="16" style="margin-right: 4px;" />
          返回
        </el-button>
        <el-button type="primary" @click="router.push(`/knowledge/${knowledgeId}/edit`)">
          <Edit :size="16" style="margin-right: 4px;" />
          编辑
        </el-button>
      </div>
    </div>

    <div v-if="loading" class="card">
      <div class="card-body">
        <el-skeleton :rows="10" animated />
      </div>
    </div>

    <template v-else-if="knowledge">
      <el-tabs v-model="activeTab" class="detail-tabs">
        <!-- Basic Info Tab -->
        <el-tab-pane label="基本信息" name="info">
          <div class="card">
            <div class="card-body">
              <el-descriptions :column="2" border>
                <el-descriptions-item label="名称" :span="2">
                  {{ knowledge.name }}
                </el-descriptions-item>
                <el-descriptions-item label="所属知识库">
                  {{ kbName || '#' + knowledge.knowledge_base_id }}
                </el-descriptions-item>
                <el-descriptions-item label="摘要" :span="1">
                  {{ knowledge.summary || '-' }}
                </el-descriptions-item>
                <el-descriptions-item label="难度">
                  <span :class="['difficulty-badge', `difficulty-badge--${getDifficultyClass(knowledge.difficulty)}`]">
                    {{ getDifficultyLabel(knowledge.difficulty) }}
                  </span>
                </el-descriptions-item>
                <el-descriptions-item label="状态">
                  <span :class="['status-badge', `status-badge--${getStatusClass(knowledge.status)}`]">
                    {{ getStatusLabel(knowledge.status) }}
                  </span>
                </el-descriptions-item>
                <el-descriptions-item label="来源">
                  {{ getSourceLabel(knowledge.source_type) }}
                </el-descriptions-item>
                <el-descriptions-item label="来源文档">
                  {{ knowledge.source_document || '-' }}
                </el-descriptions-item>
                <el-descriptions-item label="关键词" :span="2">
                  <div v-if="knowledge.keywords && knowledge.keywords.length > 0" style="display: flex; gap: 8px; flex-wrap: wrap;">
                    <el-tag v-for="(keyword, index) in knowledge.keywords" :key="index" size="small">
                      {{ keyword }}
                    </el-tag>
                  </div>
                  <span v-else>-</span>
                </el-descriptions-item>
                <el-descriptions-item label="创建时间">
                  {{ formatDate(knowledge.created_at) }}
                </el-descriptions-item>
                <el-descriptions-item label="更新时间">
                  {{ formatDate(knowledge.updated_at) }}
                </el-descriptions-item>
              </el-descriptions>
            </div>
          </div>

          <!-- Content -->
          <div class="card" style="margin-top: 16px;">
            <div class="card-header">详细内容</div>
            <div class="card-body">
              <div class="content-area" v-if="knowledge.content">
                <pre>{{ knowledge.content }}</pre>
              </div>
              <div v-else class="empty-state" style="padding: 40px;">
                <p class="description">暂无详细内容</p>
              </div>
            </div>
          </div>
        </el-tab-pane>

        <!-- Relations Tab -->
        <el-tab-pane label="知识关系" name="relations">
          <KnowledgeRelationList
            :knowledge-id="knowledgeId"
            :relations="relations"
            @refresh="fetchData"
            @delete="handleDeleteRelation"
          />
        </el-tab-pane>
      </el-tabs>
    </template>

    <!-- Error -->
    <div v-else class="card">
      <div class="empty-state">
        <p class="title">知识点不存在</p>
        <el-button type="primary" @click="router.push('/knowledge')">返回列表</el-button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.detail-tabs {
  background: var(--color-card);
  border-radius: var(--radius-lg);
  padding: 16px;
}

.content-area pre {
  font-family: var(--font-sans);
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.6;
  color: var(--color-foreground);
}
</style>
