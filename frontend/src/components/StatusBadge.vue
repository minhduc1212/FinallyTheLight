<template>
  <span :class="badgeClass">
    {{ badgeLabel }}
  </span>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  status: {
    type: String,
    default: 'pending'
  },
  type: {
    type: String,
    default: 'project', // 'project' | 'chunk'
    validator: (val) => ['project', 'chunk'].includes(val)
  }
})

// Normalize status values
const normalizedStatus = computed(() => {
  const st = props.status ? props.status.toLowerCase() : 'pending'
  if (st === 'running' || st === 'translating') return 'translating'
  if (st === 'failed' || st === 'error') return 'failed'
  if (st === 'completed' || st === 'done') return 'completed'
  return 'pending'
})

const badgeClass = computed(() => {
  switch (normalizedStatus.value) {
    case 'completed':
      return 'badge badge-completed'
    case 'translating':
      return 'badge badge-translating'
    case 'failed':
      return 'badge badge-failed'
    default:
      return 'badge badge-pending'
  }
})

const badgeLabel = computed(() => {
  if (props.type === 'project') {
    switch (normalizedStatus.value) {
      case 'translating':
        return 'Đang dịch'
      case 'failed':
        return 'Lỗi'
      case 'completed':
        return 'Hoàn tất'
      default:
        return 'Rảnh'
    }
  } else {
    // type === 'chunk'
    switch (normalizedStatus.value) {
      case 'completed':
        return 'Đã dịch'
      case 'failed':
        return 'Lỗi dịch'
      case 'translating':
        return 'Đang dịch'
      default:
        return 'Chờ dịch'
    }
  }
})
</script>
