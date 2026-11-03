<script setup lang="ts">
/**
 * 普通用户管理（管理员）
 * GET  /api/v1/admin/app-users
 * GET  /api/v1/admin/app-users/{id}
 * PATCH /api/v1/admin/app-users/{id}/status
 */
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { getAppUserList, getAppUserDetail, updateAppUserStatus } from '@/api/appUser'
import type { AppUserListItem, AppUserStatus, AppUserQueryParams } from '@/types/appUser'
import { getAppUserStatusLabel, getAppUserStatusClass } from '@/constants/appUser'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, RefreshCw, Eye, Users, ShieldCheck, ShieldOff, UserCheck } from 'lucide-vue-next'

const loading = ref(true)
const tableData = ref<AppUserListItem[]>([])
const total = ref(0)
const loadError = ref(false)

const queryParams = ref<AppUserQueryParams>({
  page: 1,
  page_size: 20,
  keyword: '',
  status: undefined,
})

// 详情弹窗
const detailVisible = ref(false)
const detailLoading = ref(false)
const detailUser = ref<AppUserListItem | null>(null)

// 状态变更 loading 锁
const statusChangingId = ref<number | null>(null)

const hasFilters = computed(() => !!queryParams.value.keyword || queryParams.value.status)

async function fetchData() {
  loading.value = true
  loadError.value = false
  try {
    const params: AppUserQueryParams = { ...queryParams.value }
    if (!params.keyword) delete params.keyword
    if (params.status === undefined || params.status === null) delete params.status

    const res = await getAppUserList(params)
    tableData.value = res.data.items
    total.value = res.data.total
  } catch {
    loadError.value = true
    tableData.value = []
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
    keyword: '',
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

async function openDetail(id: number) {
  detailVisible.value = true
  detailLoading.value = true
  detailUser.value = null
  try {
    const res = await getAppUserDetail(id)
    detailUser.value = res.data
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '获取用户详情失败')
    detailVisible.value = false
  } finally {
    detailLoading.value = false
  }
}

// 禁用/启用
async function handleToggleStatus(user: AppUserListItem) {
  const target: AppUserStatus = user.status === 'active' ? 'disabled' : 'active'
  const isDisable = target === 'disabled'

  // deleted 用户不可操作
  if (user.status === 'deleted') return

  // 确认弹窗
  const confirmText = isDisable
    ? '禁用后，该用户将无法继续登录或刷新登录状态，当前 Refresh 会话会被撤销。用户历史答题记录、试卷和练习数据会保留。请确认是否禁用。'
    : '启用后，该用户可以重新登录和使用普通用户功能。历史学习记录不会受到影响。是否继续？'

  try {
    const result = await ElMessageBox.prompt(
      confirmText,
      isDisable ? '禁用普通用户' : '启用普通用户',
      {
        confirmButtonText: isDisable ? '确认禁用' : '确认启用',
        cancelButtonText: '取消',
        inputType: 'textarea',
        inputPlaceholder: isDisable ? '请填写禁用原因（必填）' : '请填写启用原因（选填）',
        inputValidator: isDisable
          ? (v: string) => (v && v.trim().length > 0) || '请填写禁用原因'
          : undefined,
        type: isDisable ? 'warning' : 'info',
      },
    )
    const reason = result.value.trim()

    statusChangingId.value = user.id
    const res = await updateAppUserStatus(user.id, { status: target, reason })

    const revoked = res.data.revoked_sessions
    const msg = isDisable
      ? revoked > 0
        ? `已禁用，撤销了 ${revoked} 个登录会话`
        : '已禁用'
      : '已启用'
    ElMessage.success(msg)

    // 用响应更新行数据
    const idx = tableData.value.findIndex((u) => u.id === user.id)
    if (idx !== -1) {
      tableData.value[idx] = { ...tableData.value[idx], status: res.data.status } as AppUserListItem
    }
    // 同步详情弹窗
    if (detailUser.value?.id === user.id) {
      detailUser.value = { ...detailUser.value, status: res.data.status } as AppUserListItem
    }
  } catch (e) {
    // 失败保留原状态
    if (e !== 'cancel') {
      ElMessage.error(e instanceof Error ? e.message : '操作失败')
    }
  } finally {
    statusChangingId.value = null
  }
}

function formatDateTime(dt: string | null): string {
  if (!dt) return '-'
  return new Date(dt).toLocaleString('zh-CN')
}

onMounted(fetchData)
</script>

<template>
  <div class="page-container">
    <div class="page-header">
      <div>
        <h2>普通用户管理</h2>
        <p class="description">管理普通答题用户的账号状态；不涉及管理员账号</p>
      </div>
    </div>

    <!-- 筛选 -->
    <div class="filter-toolbar">
      <el-input
        v-model="queryParams.keyword"
        placeholder="账号/昵称"
        clearable
        style="width: 200px;"
        @keyup.enter="handleSearch"
      >
        <template #prefix><Search :size="16" /></template>
      </el-input>

      <el-select
        v-model="queryParams.status"
        placeholder="用户状态"
        clearable
        style="width: 130px;"
        @change="handleSearch"
      >
        <el-option label="正常" value="active" />
        <el-option label="已禁用" value="disabled" />
        <el-option label="已删除" value="deleted" />
      </el-select>

      <el-button type="primary" @click="handleSearch">
        <Search :size="16" style="margin-right: 4px;" />
        查询
      </el-button>
      <el-button @click="handleReset">
        <RefreshCw :size="16" style="margin-right: 4px;" />
        重置
      </el-button>
    </div>

    <!-- 错误 -->
    <div v-if="loadError" class="card">
      <div class="empty-state">
        <p class="title">加载失败</p>
        <p class="description">无法获取用户列表，请检查后端服务后重试</p>
        <el-button type="primary" @click="fetchData">重新加载</el-button>
      </div>
    </div>

    <!-- Loading -->
    <div v-else-if="loading" class="card">
      <div class="card-body">
        <el-skeleton :rows="8" animated />
      </div>
    </div>

    <!-- 空 -->
    <div v-else-if="tableData.length === 0" class="card">
      <div class="empty-state">
        <Users :size="48" />
        <p class="title">{{ hasFilters ? '筛选条件下暂无结果' : '暂无用户' }}</p>
        <p class="description">
          {{ hasFilters ? '请调整筛选条件后重试' : '普通用户注册后会出现在这里' }}
        </p>
      </div>
    </div>

    <!-- 表格 -->
    <div v-else class="card">
      <el-table :data="tableData" style="width: 100%;">
        <el-table-column prop="id" label="ID" width="80" align="center" />
        <el-table-column prop="account" label="账号" min-width="130" show-overflow-tooltip />
        <el-table-column prop="nickname" label="昵称" min-width="120" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.nickname || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <span :class="['status-badge', `status-badge--${getAppUserStatusClass(row.status)}`]">
              {{ getAppUserStatusLabel(row.status) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="最近登录" width="150" align="center">
          <template #default="{ row }">
            {{ row.last_login_at ? formatDateTime(row.last_login_at) : '从未登录' }}
          </template>
        </el-table-column>
        <el-table-column label="注册时间" width="150" align="center">
          <template #default="{ row }">
            {{ formatDateTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="活跃会话" width="90" align="center">
          <template #default="{ row }">
            <span :class="row.active_session_count > 0 ? 'active-text' : 'muted-text'">
              {{ row.active_session_count }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right" align="center">
          <template #default="{ row }">
            <el-button text type="primary" size="small" @click="openDetail(row.id)">
              <Eye :size="14" style="margin-right: 4px;" />
              详情
            </el-button>
            <el-button
              v-if="row.status === 'active'"
              text
              type="warning"
              size="small"
              :disabled="statusChangingId === row.id"
              @click="handleToggleStatus(row)"
            >
              <ShieldOff :size="14" style="margin-right: 4px;" />
              禁用
            </el-button>
            <el-button
              v-else-if="row.status === 'disabled'"
              text
              type="success"
              size="small"
              :disabled="statusChangingId === row.id"
              @click="handleToggleStatus(row)"
            >
              <ShieldCheck :size="14" style="margin-right: 4px;" />
              启用
            </el-button>
            <!-- deleted 用户只读，不显示操作 -->
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
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

    <!-- 详情弹窗 -->
    <el-dialog
      v-model="detailVisible"
      title="普通用户详情"
      width="520px"
      :close-on-click-modal="false"
    >
      <div v-if="detailLoading" style="padding: 20px 0;">
        <el-skeleton :rows="5" animated />
      </div>
      <template v-else-if="detailUser">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="用户 ID">{{ detailUser.id }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <span :class="['status-badge', `status-badge--${getAppUserStatusClass(detailUser.status)}`]">
              {{ getAppUserStatusLabel(detailUser.status) }}
            </span>
          </el-descriptions-item>
          <el-descriptions-item label="账号">{{ detailUser.account }}</el-descriptions-item>
          <el-descriptions-item label="昵称">{{ detailUser.nickname || '-' }}</el-descriptions-item>
          <el-descriptions-item label="注册时间" :span="2">
            {{ formatDateTime(detailUser.created_at) }}
          </el-descriptions-item>
          <el-descriptions-item label="最近登录" :span="2">
            {{ detailUser.last_login_at ? formatDateTime(detailUser.last_login_at) : '从未登录' }}
          </el-descriptions-item>
          <el-descriptions-item label="活跃会话数">
            {{ detailUser.active_session_count }}
          </el-descriptions-item>
          <el-descriptions-item v-if="detailUser.deleted_at" label="删除时间">
            {{ formatDateTime(detailUser.deleted_at) }}
          </el-descriptions-item>
        </el-descriptions>

        <div v-if="detailUser.status !== 'deleted'" class="detail-actions">
          <el-button
            v-if="detailUser.status === 'active'"
            type="warning"
            :loading="statusChangingId === detailUser.id"
            @click="handleToggleStatus(detailUser)"
          >
            <ShieldOff :size="16" style="margin-right: 4px;" />
            禁用用户
          </el-button>
          <el-button
            v-else
            type="success"
            :loading="statusChangingId === detailUser.id"
            @click="handleToggleStatus(detailUser)"
          >
            <UserCheck :size="16" style="margin-right: 4px;" />
            启用用户
          </el-button>
        </div>
        <div v-else class="deleted-hint">
          已删除用户不可恢复，不支持启用/禁用操作。
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.filter-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.muted-text {
  color: var(--color-muted-foreground);
  font-size: 12px;
}

.active-text {
  color: var(--color-success, #059669);
  font-weight: 600;
}

.detail-actions {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

.deleted-hint {
  margin-top: 12px;
  padding: 10px 14px;
  background: var(--color-muted);
  border-radius: var(--radius-md);
  font-size: 13px;
  color: var(--color-muted-foreground);
}
</style>
