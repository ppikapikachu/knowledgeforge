<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getDashboardOverview } from '@/api/dashboard'
import type { DashboardOverview } from '@/types/dashboard'
import {
  BookOpen,
  FileQuestion,
  CheckCircle,
  AlertCircle,
  XCircle,
  Upload,
} from 'lucide-vue-next'

const router = useRouter()
const loading = ref(true)
const error = ref(false)
const overview = ref<DashboardOverview | null>(null)

async function fetchDashboard() {
  loading.value = true
  error.value = false
  try {
    const res = await getDashboardOverview()
    overview.value = res.data
  } catch (err) {
    error.value = true
    console.error('Dashboard fetch error:', err)
  } finally {
    loading.value = false
  }
}

onMounted(fetchDashboard)
</script>

<template>
  <div class="page-container">
    <div class="page-header">
      <div>
        <h2>Dashboard</h2>
        <p class="description">系统数据概览</p>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="loading-state">
      <el-skeleton :rows="8" animated />
    </div>

    <!-- Content -->
    <template v-else-if="overview">
      <!-- Stats Cards -->
      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-icon" style="background: #EFF6FF; color: #2563EB;">
            <BookOpen :size="24" />
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ overview.knowledge_count }}</div>
            <div class="stat-label">知识点总数</div>
          </div>
        </div>

        <div class="stat-card">
          <div class="stat-icon" style="background: #F0FDF4; color: #059669;">
            <FileQuestion :size="24" />
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ overview.question_count }}</div>
            <div class="stat-label">题目总数</div>
          </div>
        </div>

        <div class="stat-card">
          <div class="stat-icon" style="background: #FDF4FF; color: #9333EA;">
            <CheckCircle :size="24" />
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ overview.single_choice_count }}</div>
            <div class="stat-label">单选题</div>
          </div>
        </div>

        <div class="stat-card">
          <div class="stat-icon" style="background: #FFF7ED; color: #EA580C;">
            <AlertCircle :size="24" />
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ overview.multiple_choice_count }}</div>
            <div class="stat-label">多选题</div>
          </div>
        </div>

        <div class="stat-card">
          <div class="stat-icon" style="background: #FEF2F2; color: #DC2626;">
            <XCircle :size="24" />
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ overview.true_false_count }}</div>
            <div class="stat-label">判断题</div>
          </div>
        </div>

        <div class="stat-card">
          <div class="stat-icon" style="background: #ECFDF5; color: #059669;">
            <FileQuestion :size="24" />
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ overview.short_answer_count }}</div>
            <div class="stat-label">简答题</div>
          </div>
        </div>

        <div class="stat-card">
          <div class="stat-icon" style="background: #E9D5FF; color: #7C3AED;">
            <Upload :size="24" />
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ overview.import_task_count }}</div>
            <div class="stat-label">导入任务</div>
          </div>
        </div>
      </div>
    </template>

    <!-- Error -->
    <div v-else-if="error" class="card">
      <div class="empty-state">
        <XCircle :size="48" style="color: var(--color-error);" />
        <p class="title">获取数据失败</p>
        <p class="description">请确认后端服务已启动（http://127.0.0.1:8000）</p>
        <el-button type="primary" @click="fetchDashboard">重试</el-button>
      </div>
    </div>

    <!-- No data -->
    <div v-else class="card">
      <div class="empty-state">
        <BookOpen :size="48" />
        <p class="title">暂无数据</p>
        <p class="description">系统还没有任何数据</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}

.stat-card {
  background: var(--color-card);
  border-radius: var(--radius-lg);
  padding: 20px;
  display: flex;
  align-items: center;
  gap: 16px;
  box-shadow: var(--shadow-sm);
  border: 1px solid var(--color-border);
}

.stat-icon {
  width: 48px;
  height: 48px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.stat-value {
  font-size: 24px;
  font-weight: 700;
  color: var(--color-foreground);
  line-height: 1.2;
}

.stat-label {
  font-size: 13px;
  color: var(--color-muted-foreground);
  margin-top: 4px;
}
</style>
