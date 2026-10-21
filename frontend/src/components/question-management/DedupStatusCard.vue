<script setup lang="ts">
/**
 * 去重服务状态卡片
 * GET /question-dedup/status
 * POST /question-dedup/index/rebuild
 */
import { ref, onMounted } from 'vue'
import { getDedupStatus, rebuildDedupIndex } from '@/api/questionDedup'
import type { DedupStatusData } from '@/types/questionDedup'
import {
  getDedupStatusLabel,
  getDedupStatusClass,
} from '@/constants/questionDedup'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Shield, RefreshCw, AlertTriangle, CheckCircle, Loader, Ban, Wrench } from 'lucide-vue-next'

const statusData = ref<DedupStatusData | null>(null)
const loading = ref(false)
const rebuilding = ref(false)
const error = ref(false)

async function fetchStatus() {
  loading.value = true
  error.value = false
  try {
    const res = await getDedupStatus()
    statusData.value = res.data
  } catch {
    error.value = true
    statusData.value = null
  } finally {
    loading.value = false
  }
}

function getStatusIcon(status: string) {
  switch (status) {
    case 'ready': return CheckCircle
    case 'initializing': return Loader
    case 'degraded': return AlertTriangle
    case 'disabled': return Ban
    default: return Shield
  }
}

async function handleRebuild() {
  try {
    await ElMessageBox.confirm(
      '重建题目向量索引可能耗费资源，期间语义检索状态可能变化。是否继续？',
      '重建索引确认',
      { confirmButtonText: '开始重建', cancelButtonText: '取消', type: 'warning' },
    )
  } catch {
    return
  }

  rebuilding.value = true
  try {
    const res = await rebuildDedupIndex(true)
    statusData.value = res.data
    ElMessage.success('索引重建完成')
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '索引重建失败')
  } finally {
    rebuilding.value = false
  }
}

onMounted(fetchStatus)

defineExpose({ fetchStatus })
</script>

<template>
  <div class="dedup-status-card">
    <div class="card-header">
      <Shield :size="18" style="margin-right: 8px;" />
      语义去重服务状态
      <el-button text size="small" style="margin-left: auto;" @click="fetchStatus" :loading="loading">
        <RefreshCw :size="14" style="margin-right: 4px;" />
        刷新
      </el-button>
    </div>
    <div class="card-body">
      <!-- 加载中 -->
      <div v-if="loading && !statusData" class="status-loading">
        <el-skeleton :rows="2" animated />
      </div>

      <!-- 错误 -->
      <div v-else-if="error" class="status-error">
        <AlertTriangle :size="18" />
        <span>状态获取失败，请检查后端服务</span>
        <el-button size="small" @click="fetchStatus">重试</el-button>
      </div>

      <!-- 状态展示 -->
      <template v-else-if="statusData">
        <div class="status-row">
          <span :class="['status-icon-wrapper', `s-${getDedupStatusClass(statusData.status)}`]">
            <component :is="getStatusIcon(statusData.status)" :size="20" />
          </span>
          <div class="status-info">
            <div class="status-label" :class="`text-${getDedupStatusClass(statusData.status)}`">
              {{ getDedupStatusLabel(statusData.status) }}
            </div>
            <div v-if="statusData.reason" class="status-reason">{{ statusData.reason }}</div>
          </div>
          <el-button
            v-if="statusData.status !== 'disabled'"
            type="primary"
            plain
            size="small"
            :loading="rebuilding"
            @click="handleRebuild"
          >
            <Wrench :size="14" style="margin-right: 4px;" />
            重建索引
          </el-button>
        </div>

        <!-- 诊断信息 -->
        <div class="status-meta">
          <div class="meta-item">
            <span class="meta-label">阻断题目数</span>
            <span class="meta-value">{{ statusData.blocking_question_count }}</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">指纹版本</span>
            <span class="meta-value">v{{ statusData.hash_version }}</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">功能开关</span>
            <span class="meta-value">{{ statusData.enabled ? '已启用' : '已关闭' }}</span>
          </div>
        </div>

        <!-- 失败信息 -->
        <div v-if="statusData.failures && statusData.failures.length > 0" class="status-failures">
          <AlertTriangle :size="14" />
          {{ statusData.failures.length }} 条索引写入失败
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.dedup-status-card {
  background: var(--color-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  overflow: hidden;
}

.dedup-status-card .card-header {
  display: flex;
  align-items: center;
  padding: 12px 16px;
  font-size: 14px;
  font-weight: 600;
  color: var(--color-foreground);
  border-bottom: 1px solid var(--color-border);
}

.dedup-status-card .card-body {
  padding: 16px;
}

.status-loading {
  padding: 8px 0;
}

.status-error {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--color-error, #DC2626);
  font-size: 13px;
}

.status-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.status-icon-wrapper {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.status-icon-wrapper.s-success {
  background: #ECFDF5;
  color: var(--color-success, #059669);
}

.status-icon-wrapper.s-info {
  background: #EFF6FF;
  color: var(--color-info, #2563EB);
}

.status-icon-wrapper.s-error {
  background: #FEF2F2;
  color: var(--color-error, #DC2626);
}

.status-icon-wrapper.s-warning {
  background: #FFFBEB;
  color: var(--color-warning, #D97706);
}

.status-icon-wrapper.s-muted {
  background: var(--color-muted);
  color: var(--color-muted-foreground);
}

.status-info {
  flex: 1;
}

.status-label {
  font-size: 15px;
  font-weight: 600;
}

.text-success { color: var(--color-success, #059669); }
.text-info { color: var(--color-info, #2563EB); }
.text-error { color: var(--color-error, #DC2626); }
.text-warning { color: var(--color-warning, #D97706); }
.text-muted { color: var(--color-muted-foreground); }

.status-reason {
  font-size: 12px;
  color: var(--color-muted-foreground);
  margin-top: 2px;
}

.status-meta {
  display: flex;
  gap: 24px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--color-border);
}

.meta-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.meta-label {
  font-size: 11px;
  color: var(--color-muted-foreground);
}

.meta-value {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-foreground);
}

.status-failures {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 8px;
  padding: 6px 10px;
  background: #FEF2F2;
  border-radius: var(--radius-md);
  font-size: 12px;
  color: var(--color-error, #DC2626);
}
</style>
