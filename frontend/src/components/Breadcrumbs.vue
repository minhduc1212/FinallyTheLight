<template>
  <nav class="breadcrumb">
    <router-link to="/dashboard" class="breadcrumb-item">Bảng điều khiển</router-link>
    <template v-for="(crumb, index) in breadcrumbs" :key="index">
      <span class="breadcrumb-separator">›</span>
      <router-link
        v-if="crumb.to"
        :to="crumb.to"
        class="breadcrumb-item"
      >
        {{ crumb.label }}
      </router-link>
      <span v-else class="breadcrumb-current">{{ crumb.label }}</span>
    </template>
  </nav>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()

const breadcrumbs = computed(() => {
  const crumbs = []
  const path = route.path
  const currentProject = route.params.project || null
  const currentNovel = route.params.novel || null

  if (path.includes('/settings')) {
    crumbs.push({ label: 'Thiết lập Toàn cục', to: null })
  } else if (currentProject) {
    crumbs.push({ label: 'Dự án', to: '/dashboard/projects' })
    
    if (path.includes('/glossary')) {
      crumbs.push({ label: currentProject, to: `/dashboard/${currentProject}` })
      crumbs.push({ label: 'Thuật ngữ', to: null })
    } else if (currentNovel) {
      crumbs.push({ label: currentProject, to: `/dashboard/${currentProject}` })
      crumbs.push({ label: currentNovel, to: null })
    } else {
      crumbs.push({ label: currentProject, to: null })
    }
  } else if (path === '/dashboard' || path === '/dashboard/' || path === '/dashboard/projects') {
    crumbs.push({ label: 'Dự án', to: null })
  }

  return crumbs
})
</script>
