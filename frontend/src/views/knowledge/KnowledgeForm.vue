<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getKnowledgeDetail, createKnowledge, updateKnowledge } from '@/api/knowledge'
import type { KnowledgeCreateRequest } from '@/types/knowledge'
import { ElMessage } from 'element-plus'
import { Save, ArrowLeft } from 'lucide-vue-next'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const saving = ref(false)

const isEdit = computed(() => !!route.params.id)
const knowledgeId = computed(() => Number(route.params.id))

const form = ref<KnowledgeCreateRequest>({
  name: '',
  summary: null,
  content: null,
  difficulty: 1,
  status: 1,
  source_type: 'MANUAL',
  source_document: null,
  keywords: null,
})

const keywordInput = ref('')

const rules = {
  name: [
    { required: true, message: '请输入知识点名称', trigger: 'blur' },
    { max: 200, message: '名称不超过200字符', trigger: 'blur' },
  ],
  difficulty: [
    { required: true, message: '请选择难度', trigger: 'change' },
  ],
}

const formRef = ref()

const difficultyOptions = [
  { label: '简单', value: 1 },
  { label: '中等', value: 2 },
  { label: '困难', value: 3 },
]

const statusOptions = [
  { label: '正常', value: 1 },
  { label: '禁用', value: 0 },
]

const sourceOptions = [
  { label: '手工', value: 'MANUAL' },
  { label: '导入', value: 'IMPORT' },
  { label: 'AI', value: 'AI' },
]

async function fetchDetail() {
  if (!isEdit.value) return
  loading.value = true
  try {
    const res = await getKnowledgeDetail(knowledgeId.value)
    const data = res.data
    form.value = {
      name: data.name,
      summary: data.summary || '',
      content: data.content || '',
      difficulty: data.difficulty,
      status: data.status,
      source_type: data.source_type,
      source_document: data.source_document || null,
      keywords: data.keywords ? (data.keywords as string[]) : null,
    }
  } catch {
    ElMessage.error('获取知识点详情失败')
  } finally {
    loading.value = false
  }
}

async function handleSubmit() {
  try {
    await formRef.value?.validate()
  } catch {
    return
  }

  saving.value = true
  try {
    if (isEdit.value) {
      await updateKnowledge(knowledgeId.value, form.value)
      ElMessage.success('更新成功')
    } else {
      await createKnowledge(form.value)
      ElMessage.success('创建成功')
    }
    router.push('/knowledge')
  } catch {
    // Error handled by interceptor
  } finally {
    saving.value = false
  }
}

function addKeyword() {
  const keyword = keywordInput.value.trim()
  if (keyword) {
    if (!form.value.keywords) form.value.keywords = []
    if (!form.value.keywords.includes(keyword)) {
      form.value.keywords.push(keyword)
    }
    keywordInput.value = ''
  }
}

function removeKeyword(index: number) {
  form.value.keywords?.splice(index, 1)
}

onMounted(fetchDetail)
</script>

<template>
  <div class="page-container">
    <div class="page-header">
      <div>
        <h2>{{ isEdit ? '编辑知识点' : '新增知识点' }}</h2>
        <p class="description">{{ isEdit ? '修改知识点信息' : '创建新的知识点' }}</p>
      </div>
      <el-button @click="router.back()">
        <ArrowLeft :size="16" style="margin-right: 4px;" />
        返回
      </el-button>
    </div>

    <div v-if="loading" class="card">
      <div class="card-body">
        <el-skeleton :rows="10" animated />
      </div>
    </div>

    <div v-else class="card">
      <div class="card-body">
        <el-form
          ref="formRef"
          :model="form"
          :rules="rules"
          label-width="100px"
          label-position="right"
          size="large"
          style="max-width: 800px;"
        >
          <el-form-item label="名称" prop="name">
            <el-input v-model="form.name" placeholder="请输入知识点名称" maxlength="200" show-word-limit />
          </el-form-item>

          <el-form-item label="摘要">
            <el-input
              v-model="form.summary"
              type="textarea"
              :rows="3"
              placeholder="请输入知识点摘要"
              maxlength="500"
              show-word-limit
            />
          </el-form-item>

          <el-form-item label="详细内容">
            <el-input
              v-model="form.content"
              type="textarea"
              :rows="10"
              placeholder="请输入知识点详细内容"
            />
          </el-form-item>

          <el-form-item label="难度" prop="difficulty">
            <el-radio-group v-model="form.difficulty">
              <el-radio-button
                v-for="item in difficultyOptions"
                :key="item.value"
                :value="item.value"
              >
                {{ item.label }}
              </el-radio-button>
            </el-radio-group>
          </el-form-item>

          <el-form-item label="状态">
            <el-radio-group v-model="form.status">
              <el-radio-button
                v-for="item in statusOptions"
                :key="item.value"
                :value="item.value"
              >
                {{ item.label }}
              </el-radio-button>
            </el-radio-group>
          </el-form-item>

          <el-form-item label="来源">
            <el-select v-model="form.source_type" style="width: 200px;">
              <el-option
                v-for="item in sourceOptions"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
          </el-form-item>

          <el-form-item label="关键词">
            <div class="keyword-input-wrapper">
              <el-input
                v-model="keywordInput"
                placeholder="输入关键词后按 Enter"
                style="width: 300px;"
                @keyup.enter="addKeyword"
              />
              <el-button @click="addKeyword">添加</el-button>
            </div>
            <div class="keyword-tags" v-if="form.keywords && form.keywords.length > 0">
              <el-tag
                v-for="(keyword, index) in form.keywords"
                :key="index"
                closable
                @close="removeKeyword(index)"
              >
                {{ keyword }}
              </el-tag>
            </div>
          </el-form-item>

          <el-form-item>
            <el-button type="primary" :loading="saving" @click="handleSubmit">
              <Save :size="16" style="margin-right: 4px;" />
              {{ isEdit ? '保存修改' : '创建知识点' }}
            </el-button>
            <el-button @click="router.back()">取消</el-button>
          </el-form-item>
        </el-form>
      </div>
    </div>
  </div>
</template>

<style scoped>
.keyword-input-wrapper {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.keyword-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
</style>
