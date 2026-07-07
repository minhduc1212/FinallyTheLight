<template>
  <div class="dashboard-wrapper">
    <!-- Nav Bar -->
    <nav class="navbar">
      <div class="nav-container">
        <div class="nav-left" @click="router.push('/')">
          <span class="wordmark">Finally The Light</span>
        </div>
        <div class="nav-right">
          <slot name="header-actions"></slot>
        </div>
      </div>
    </nav>

    <!-- Dashboard Body -->
    <div class="dashboard-body">
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
          <div class="sidebar-divider" style="margin-top: auto; border-top: 1px solid var(--hairline);"></div>
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

      <!-- Main Content Area -->
      <main style="flex: 1; overflow-y: auto;">
        <div class="dashboard-content">
          <!-- Breadcrumb Navigation -->
          <Breadcrumbs />

          <!-- Page Content slot -->
          <div class="content-inner">
            <slot></slot>
          </div>
        </div>
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import Breadcrumbs from '@/components/Breadcrumbs.vue'

const route = useRoute()
const router = useRouter()

// Get current project from route parameters
const currentProject = computed(() => route.params.project || null)

// Computations for active sidebar links
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
</script>

<style scoped>
.sidebar-divider {
  margin: 16px 0;
}
</style>
