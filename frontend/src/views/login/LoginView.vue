<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { ElMessage } from 'element-plus'
import { User, Lock, Eye, EyeOff } from 'lucide-vue-next'

const authStore = useAuthStore()
const showPassword = ref(false)

const form = reactive({
  username: '',
  password: '',
})

const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码至少6位', trigger: 'blur' },
  ],
}

const formRef = ref()

async function handleLogin() {
  try {
    await formRef.value?.validate()
  } catch {
    return
  }

  try {
    await authStore.login(form.username, form.password)
    ElMessage.success('登录成功')
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : '登录失败'
    ElMessage.error(message)
  }
}
</script>

<template>
  <div class="login-page">
    <div class="login-container">
      <!-- Left: Brand -->
      <div class="login-brand">
        <div class="brand-content">
          <h1 class="brand-title">KnowledgeForge</h1>
          <p class="brand-subtitle">AI 面试题库与知识库管理系统</p>
          <div class="brand-features">
            <div class="feature-item">
              <BookOpen :size="20" />
              <span>智能知识管理</span>
            </div>
            <div class="feature-item">
              <FileQuestion :size="20" />
              <span>题库自动构建</span>
            </div>
            <div class="feature-item">
              <Brain :size="20" />
              <span>AI 驱动分析</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Right: Login Form -->
      <div class="login-form-wrapper">
        <div class="login-form-container">
          <h2 class="form-title">管理员登录</h2>
          <p class="form-desc">请输入您的账号和密码</p>

          <el-form
            ref="formRef"
            :model="form"
            :rules="rules"
            label-position="top"
            size="large"
            @submit.prevent="handleLogin"
          >
            <el-form-item label="用户名" prop="username">
              <el-input
                v-model="form.username"
                placeholder="请输入用户名"
                :prefix-icon="User"
                clearable
              />
            </el-form-item>

            <el-form-item label="密码" prop="password">
              <el-input
                v-model="form.password"
                :type="showPassword ? 'text' : 'password'"
                placeholder="请输入密码"
                :prefix-icon="Lock"
                @keyup.enter="handleLogin"
              >
                <template #suffix>
                  <el-icon
                    class="password-toggle"
                    @click="showPassword = !showPassword"
                  >
                    <EyeOff v-if="showPassword" :size="18" />
                    <Eye v-else :size="18" />
                  </el-icon>
                </template>
              </el-input>
            </el-form-item>

            <el-form-item>
              <el-button
                type="primary"
                :loading="authStore.loading"
                class="login-btn"
                @click="handleLogin"
              >
                {{ authStore.loading ? '登录中...' : '登录' }}
              </el-button>
            </el-form-item>
          </el-form>
        </div>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
import { BookOpen, FileQuestion, Brain } from 'lucide-vue-next'
export default {
  components: { BookOpen, FileQuestion, Brain }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-background);
  padding: 20px;
}

.login-container {
  display: flex;
  width: 100%;
  max-width: 900px;
  background: var(--color-card);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-lg);
  overflow: hidden;
  min-height: 520px;
}

/* Left brand section */
.login-brand {
  flex: 1;
  background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-primary-light) 100%);
  padding: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
}

.brand-content {
  text-align: center;
}

.brand-title {
  font-size: 32px;
  font-weight: 700;
  margin-bottom: 12px;
}

.brand-subtitle {
  font-size: 16px;
  opacity: 0.9;
  margin-bottom: 40px;
}

.brand-features {
  display: flex;
  flex-direction: column;
  gap: 16px;
  text-align: left;
}

.feature-item {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 14px;
  opacity: 0.9;
}

/* Right form section */
.login-form-wrapper {
  flex: 1;
  padding: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.login-form-container {
  width: 100%;
  max-width: 320px;
}

.form-title {
  font-size: 24px;
  font-weight: 600;
  color: var(--color-foreground);
  margin-bottom: 8px;
}

.form-desc {
  font-size: 14px;
  color: var(--color-muted-foreground);
  margin-bottom: 32px;
}

.login-btn {
  width: 100%;
  height: 44px;
  font-size: 16px;
}

.password-toggle {
  cursor: pointer;
  color: var(--color-muted-foreground);
}

.password-toggle:hover {
  color: var(--color-foreground);
}

/* Responsive */
@media (max-width: 768px) {
  .login-brand {
    display: none;
  }

  .login-form-wrapper {
    padding: 32px 24px;
  }
}
</style>
