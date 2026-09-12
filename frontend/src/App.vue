<script setup lang="ts">
import { useAuthStore } from '@/stores/auth'
import { onMounted } from 'vue'

const authStore = useAuthStore()

onMounted(() => {
  if (authStore.isLoggedIn()) {
    authStore.fetchUser()
  }
})
</script>

<template>
  <router-view />
</template>

<style scoped>
</style>
