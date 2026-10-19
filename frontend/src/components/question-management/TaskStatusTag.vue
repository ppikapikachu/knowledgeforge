<script setup lang="ts">
import { TASK_STATUS_LABELS, TASK_STATUS_CLASSES } from '@/constants/questionManagement'

const props = defineProps<{ status: string }>()
</script>

<template>
  <span :class="['status-badge', `status-badge--${TASK_STATUS_CLASSES[props.status] || 'muted'}`]">
    {{ TASK_STATUS_LABELS[props.status] || props.status }}
  </span>
</template>
