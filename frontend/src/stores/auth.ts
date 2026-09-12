import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { AdminUser } from '@/types/auth'
import { login as loginApi, getMe } from '@/api/auth'
import { getToken, setToken, removeToken } from '@/utils/storage'
import router from '@/router'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(getToken())
  const user = ref<AdminUser | null>(null)
  const loading = ref(false)

  async function login(username: string, password: string) {
    loading.value = true
    try {
      const res = await loginApi({ username, password })
      token.value = res.data.access_token
      setToken(res.data.access_token)
      await fetchUser()
      router.push('/dashboard')
    } finally {
      loading.value = false
    }
  }

  async function fetchUser() {
    try {
      const res = await getMe()
      user.value = res.data
    } catch {
      logout()
    }
  }

  function logout() {
    token.value = null
    user.value = null
    removeToken()
    router.push('/login')
  }

  function isLoggedIn() {
    return !!token.value
  }

  return {
    token,
    user,
    loading,
    login,
    fetchUser,
    logout,
    isLoggedIn,
  }
})
