<script setup lang="ts">
import { useAuthStore } from '@/stores/auth'
import { ElMessageBox } from 'element-plus'
import { User, LogOut, Clock } from 'lucide-vue-next'

const authStore = useAuthStore()

async function handleLogout() {
  try {
    await ElMessageBox.confirm('确定要退出登录吗？', '退出登录', {
      confirmButtonText: '确认退出',
      cancelButtonText: '取消',
      type: 'warning',
    })
    authStore.logout()
  } catch {
    // Cancelled
  }
}

function formatDate(dateStr: string | null) {
  if (!dateStr) return '从未登录'
  return new Date(dateStr).toLocaleString('zh-CN')
}
</script>

<template>
  <div class="page-container">
    <div class="page-header">
      <div>
        <h2>管理员信息</h2>
        <p class="description">当前登录的管理员账号信息</p>
      </div>
    </div>

    <div class="card" style="max-width: 600px;">
      <div class="card-body">
        <div class="admin-profile">
          <div class="profile-avatar">
            <User :size="48" />
          </div>
          <div class="profile-info">
            <div class="profile-name">
              {{ authStore.user?.nickname || authStore.user?.username || '-' }}
            </div>
            <div class="profile-username">
              @{{ authStore.user?.username || '-' }}
            </div>
          </div>
        </div>

        <el-divider />

        <el-descriptions :column="1" border>
          <el-descriptions-item label="用户ID">
            {{ authStore.user?.id || '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="用户名">
            {{ authStore.user?.username || '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="昵称">
            {{ authStore.user?.nickname || '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            <span :class="['status-badge', authStore.user?.status === 1 ? 'status-badge--success' : 'status-badge--muted']">
              {{ authStore.user?.status === 1 ? '正常' : '禁用' }}
            </span>
          </el-descriptions-item>
          <el-descriptions-item label="最后登录">
            <div style="display: flex; align-items: center; gap: 8px;">
              <Clock :size="16" style="color: var(--color-muted-foreground);" />
              {{ formatDate(authStore.user?.last_login_at || null) }}
            </div>
          </el-descriptions-item>
          <el-descriptions-item label="创建时间">
            {{ authStore.user?.created_at ? new Date(authStore.user.created_at).toLocaleString('zh-CN') : '-' }}
          </el-descriptions-item>
        </el-descriptions>

        <div style="margin-top: 24px;">
          <el-button type="danger" @click="handleLogout">
            <LogOut :size="16" style="margin-right: 4px;" />
            退出登录
          </el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.admin-profile {
  display: flex;
  align-items: center;
  gap: 20px;
}

.profile-avatar {
  width: 72px;
  height: 72px;
  border-radius: 50%;
  background: var(--color-muted);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-muted-foreground);
}

.profile-name {
  font-size: 20px;
  font-weight: 600;
  color: var(--color-foreground);
}

.profile-username {
  font-size: 14px;
  color: var(--color-muted-foreground);
  margin-top: 4px;
}
</style>
