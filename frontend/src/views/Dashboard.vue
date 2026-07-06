<template>
  <div class="dashboard-page">
    <!-- Nav Bar -->
    <nav class="navbar">
      <div class="nav-container">
        <div class="nav-left" @click="router.push('/')">
          <span class="wordmark">Finally The Light</span>
        </div>
        <div class="nav-right"></div>
      </div>
    </nav>

    <!-- Dashboard Layout -->
    <div class="dashboard-layout">
      <!-- Sidebar -->
      <aside class="sidebar">
        <!-- Main Menu -->
        <div class="sidebar-section-title">Bảng điều khiển</div>
        <div class="sidebar-menu">
          <router-link
            to="/dashboard/projects"
            class="sidebar-item"
            :class="{ active: isProjectsActive }"
            data-tooltip="Quản lý dự án: Tạo, xóa và truy cập dự án dịch thuật"
          >
            Quản lý Dự án
          </router-link>
          <router-link
            to="/dashboard/settings"
            class="sidebar-item"
            :class="{ active: isSettingsActive }"
            data-tooltip="Thiết lập toàn cục: Cấu hình API key, mô hình và tham số dịch"
          >
            Thiết lập Toàn cục
          </router-link>
        </div>

        <!-- Project Section (when project is selected) -->
        <template v-if="currentProject">
          <div class="sidebar-divider" style="margin-top: auto;"></div>
          <div class="sidebar-section-title">DỰ ÁN: {{ currentProject }}</div>
          <div class="sidebar-menu">
            <router-link
              :to="`/dashboard/${currentProject}`"
              class="sidebar-item"
              :class="{ active: isNovelsActive }"
              data-tooltip="Tiểu thuyết: Quản lý và dịch các tiểu thuyết trong dự án"
            >
              Tiểu thuyết
            </router-link>
            <router-link
              :to="`/dashboard/${currentProject}/glossary`"
              class="sidebar-item"
              :class="{ active: isGlossaryActive }"
              data-tooltip="Thuật ngữ: Quản lý bảng thuật ngữ và tên riêng của dự án"
            >
              Thuật ngữ
            </router-link>
          </div>
        </template>
      </aside>

      <!-- Main Content -->
      <main class="dashboard-main">
        <div class="dashboard-content">
          <!-- Breadcrumb -->
          <nav class="breadcrumb">
            <router-link to="/dashboard" class="breadcrumb-link">Bảng điều khiển</router-link>
            <template v-for="(crumb, index) in breadcrumbs" :key="index">
              <span class="breadcrumb-sep">›</span>
              <router-link
                v-if="crumb.to"
                :to="crumb.to"
                class="breadcrumb-link"
              >{{ crumb.label }}</router-link>
              <span v-else class="breadcrumb-current">{{ crumb.label }}</span>
            </template>
          </nav>

          <!-- Child Routes -->
          <router-view></router-view>
        </div>
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

// Current project from route params
const currentProject = computed(() => route.params.project || null)

// Active states for sidebar items
const isProjectsActive = computed(() => {
  const path = route.path
  return path === '/dashboard' || path === '/dashboard/' || path === '/dashboard/projects'
})

const isSettingsActive = computed(() => {
  return route.path.includes('/settings')
})

const isNovelsActive = computed(() => {
  if (!currentProject.value) return false
  return route.path === `/dashboard/${currentProject.value}` || route.path.includes('/novels/')
})

const isGlossaryActive = computed(() => {
  if (!currentProject.value) return false
  return route.path.includes('/glossary')
})

// Breadcrumb computation
const breadcrumbs = computed(() => {
  const crumbs = []
  const path = route.path

  if (path.includes('/settings')) {
    crumbs.push({ label: 'Thiết lập Toàn cục', to: null })
  } else if (currentProject.value) {
    crumbs.push({ label: 'Dự án', to: '/dashboard/projects' })
    
    if (path.includes('/glossary')) {
      crumbs.push({ label: currentProject.value, to: `/dashboard/${currentProject.value}` })
      crumbs.push({ label: 'Thuật ngữ', to: null })
    } else if (route.params.novel) {
      crumbs.push({ label: currentProject.value, to: `/dashboard/${currentProject.value}` })
      crumbs.push({ label: route.params.novel, to: null })
    } else {
      crumbs.push({ label: currentProject.value, to: null })
    }
  } else if (path === '/dashboard' || path === '/dashboard/' || path === '/dashboard/projects') {
    crumbs.push({ label: 'Dự án', to: null })
  }

  return crumbs
})
</script>

<style scoped>
.dashboard-page {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background-color: var(--color-bone);
}
</style>
