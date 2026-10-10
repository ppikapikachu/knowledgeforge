<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import {
  LayoutDashboard,
  BookOpen,
  GitBranch,
  FileQuestion,
  Upload,
  Settings,
  LogOut,
  PanelLeftClose,
  PanelLeft,
  User,
  Database,
} from 'lucide-vue-next'
import { ElDropdown, ElDropdownMenu, ElDropdownItem, ElMessageBox } from 'element-plus'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const isCollapsed = ref(false)

const menuItems = [
  {
    label: 'Dashboard',
    icon: LayoutDashboard,
    path: '/dashboard',
  },
  {
    label: '知识库',
    icon: Database,
    path: '/knowledge-bases',
  },
  {
    label: '知识点',
    icon: BookOpen,
    children: [
      { label: '知识点管理', path: '/knowledge' },
      { label: '知识关系', path: '/knowledge-relations' },
    ],
  },
  {
    label: '题库',
    icon: FileQuestion,
    children: [{ label: '题目', path: '/questions' }],
  },
  {
    label: '导入任务',
    icon: Upload,
    path: '/import-tasks',
  },
  {
    label: '系统',
    icon: Settings,
    children: [{ label: '管理员', path: '/admin' }],
  },
]

const expandedMenus = ref<string[]>(['知识点', '题库', '系统'])

const breadcrumbs = computed(() => {
  const matched = route.matched.filter((item) => item.meta?.title)
  return matched.map((item) => ({
    title: item.meta.title as string,
    path: item.path,
  }))
})

function toggleCollapse() {
  isCollapsed.value = !isCollapsed.value
}

function toggleSubmenu(label: string) {
  const index = expandedMenus.value.indexOf(label)
  if (index > -1) {
    expandedMenus.value.splice(index, 1)
  } else {
    expandedMenus.value.push(label)
  }
}

function isActive(path: string) {
  return route.path === path || route.path.startsWith(path + '/')
}

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
</script>

<template>
  <div class="admin-layout">
    <!-- Sidebar -->
    <aside class="sidebar" :class="{ collapsed: isCollapsed }">
      <div class="sidebar-header">
        <div class="logo" v-if="!isCollapsed">
          <span class="logo-text">KnowledgeForge</span>
        </div>
        <div class="logo-collapsed" v-else>
          <span>KF</span>
        </div>
      </div>

      <nav class="sidebar-nav">
        <template v-for="item in menuItems" :key="item.label">
          <!-- Single menu item -->
          <div
            v-if="item.path"
            class="nav-item"
            :class="{ active: isActive(item.path) }"
            @click="router.push(item.path)"
          >
            <component :is="item.icon" :size="20" />
            <span v-if="!isCollapsed" class="nav-label">{{ item.label }}</span>
          </div>

          <!-- Submenu -->
          <div v-else class="nav-group">
            <div
              class="nav-item nav-group-header"
              @click="toggleSubmenu(item.label)"
            >
              <component :is="item.icon" :size="20" />
              <span v-if="!isCollapsed" class="nav-label">{{ item.label }}</span>
              <span v-if="!isCollapsed" class="nav-arrow" :class="{ expanded: expandedMenus.includes(item.label) }">
                ▸
              </span>
            </div>
            <div
              v-if="expandedMenus.includes(item.label) && !isCollapsed"
              class="nav-submenu"
            >
              <div
                v-for="child in item.children"
                :key="child.path"
                class="nav-item nav-child"
                :class="{ active: isActive(child.path) }"
                @click="router.push(child.path)"
              >
                <span class="nav-label">{{ child.label }}</span>
              </div>
            </div>
          </div>
        </template>
      </nav>
    </aside>

    <!-- Main content -->
    <div class="main-wrapper" :class="{ expanded: isCollapsed }">
      <!-- Header -->
      <header class="header">
        <div class="header-left">
          <button class="collapse-btn" @click="toggleCollapse">
            <PanelLeftClose v-if="!isCollapsed" :size="20" />
            <PanelLeft v-else :size="20" />
          </button>
          <el-breadcrumb separator="/">
            <el-breadcrumb-item :to="{ path: '/dashboard' }">首页</el-breadcrumb-item>
            <el-breadcrumb-item v-for="item in breadcrumbs" :key="item.path">
              {{ item.title }}
            </el-breadcrumb-item>
          </el-breadcrumb>
        </div>

        <div class="header-right">
          <el-dropdown trigger="click">
            <div class="user-info">
              <User :size="20" />
              <span v-if="authStore.user" class="username">{{ authStore.user.nickname || authStore.user.username }}</span>
            </div>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="router.push('/admin')">
                  <Settings :size="16" style="margin-right: 8px;" />
                  管理员信息
                </el-dropdown-item>
                <el-dropdown-item divided @click="handleLogout">
                  <LogOut :size="16" style="margin-right: 8px;" />
                  退出登录
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </header>

      <!-- Page content -->
      <main class="main-content">
        <router-view />
      </main>
    </div>
  </div>
</template>

<style scoped>
.admin-layout {
  display: flex;
  min-height: 100vh;
}

/* Sidebar */
.sidebar {
  width: 240px;
  background: var(--color-card);
  border-right: 1px solid var(--color-border);
  display: flex;
  flex-direction: column;
  transition: width 0.2s ease;
  position: fixed;
  top: 0;
  left: 0;
  bottom: 0;
  z-index: 100;
}

.sidebar.collapsed {
  width: 64px;
}

.sidebar-header {
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-bottom: 1px solid var(--color-border);
  padding: 0 16px;
}

.logo {
  display: flex;
  align-items: center;
  gap: 8px;
}

.logo-text {
  font-size: 18px;
  font-weight: 700;
  color: var(--color-primary);
  white-space: nowrap;
}

.logo-collapsed {
  font-size: 16px;
  font-weight: 700;
  color: var(--color-primary);
}

.sidebar-nav {
  flex: 1;
  padding: 8px;
  overflow-y: auto;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border-radius: var(--radius-md);
  cursor: pointer;
  color: var(--color-muted-foreground);
  transition: all 0.15s ease;
  user-select: none;
}

.nav-item:hover {
  background: var(--color-muted);
  color: var(--color-foreground);
}

.nav-item.active {
  background: var(--color-primary);
  color: var(--color-on-primary);
}

.nav-item.active:hover {
  background: var(--color-primary-light);
}

.nav-label {
  font-size: 14px;
  white-space: nowrap;
  flex: 1;
}

.nav-arrow {
  font-size: 12px;
  transition: transform 0.2s ease;
}

.nav-arrow.expanded {
  transform: rotate(90deg);
}

.nav-submenu {
  padding-left: 32px;
}

.nav-child {
  padding: 8px 12px;
  font-size: 13px;
}

.nav-child::before {
  content: '';
  display: inline-block;
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: var(--color-muted-foreground);
  margin-right: 8px;
}

.nav-child.active::before {
  background: var(--color-on-primary);
}

/* Main wrapper */
.main-wrapper {
  flex: 1;
  margin-left: 240px;
  transition: margin-left 0.2s ease;
  display: flex;
  flex-direction: column;
}

.main-wrapper.expanded {
  margin-left: 64px;
}

/* Header */
.header {
  height: 56px;
  background: var(--color-card);
  border-bottom: 1px solid var(--color-border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  position: sticky;
  top: 0;
  z-index: 50;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.collapse-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: none;
  background: transparent;
  border-radius: var(--radius-md);
  cursor: pointer;
  color: var(--color-muted-foreground);
  transition: all 0.15s ease;
}

.collapse-btn:hover {
  background: var(--color-muted);
  color: var(--color-foreground);
}

.header-right {
  display: flex;
  align-items: center;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  border-radius: var(--radius-md);
  cursor: pointer;
  color: var(--color-foreground);
  transition: background 0.15s ease;
}

.user-info:hover {
  background: var(--color-muted);
}

.username {
  font-size: 14px;
  font-weight: 500;
}

/* Main content */
.main-content {
  flex: 1;
  overflow-y: auto;
}
</style>
