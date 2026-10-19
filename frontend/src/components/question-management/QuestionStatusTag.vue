<script setup lang="ts">
import { computed } from 'vue'
import { questionStatusLabel, questionStatusClass } from '@/constants/questionManagement'

const props = defineProps<{ status: string }>()

const label = computed(() => questionStatusLabel(props.status))
const cls = computed(() => questionStatusClass(props.status))
</script>

<template>
  <span :class="['status-badge', `status-badge--${cls}`]">
    {{ label }}
  </span>
</template>
