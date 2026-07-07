<template>
  <div class="projects-page">
    <!-- Page Header -->
    <div class="page-header">
      <h2>Quản lý Dự án</h2>
      <form class="page-header-actions" @submit.prevent="createProject">
        <input
          v-model="newProjectName"
          type="text"
          class="form-input"
          placeholder="Tên dự án mới…"
          style="width: 240px;"
        />
        <button type="submit" class="btn btn-filled" :disabled="!newProjectName.trim()">
          Thêm Dự án
        </button>
      </form>
    </div>

    <!-- Projects Table -->
    <div class="data-table-wrapper">
      <table class="data-table" v-if="projects.length > 0">
        <thead>
          <tr>
            <th style="width: 60px;">#</th>
            <th>Tên Dự án</th>
            <th>Tiểu thuyết</th>
            <th>Trạng thái</th>
            <th style="width: 200px;">Hành động</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(project, index) in projects" :key="project">
            <td>{{ index + 1 }}</td>
            <td>
              <a
                class="project-link"
                @click="router.push(`/dashboard/${project}`)"
              >
                {{ project }}
              </a>
            </td>
            <td>{{ novelCounts[project] ?? '—' }}</td>
            <td>
              <StatusBadge :status="statuses[project]?.status" type="project" />
            </td>
            <td>
              <div class="col-actions">
                <button
                  class="btn btn-outline"
                  @click="router.push(`/dashboard/${project}`)"
                >
                  Mở
                </button>
                <button
                  class="btn btn-danger"
                  @click="confirmDelete(project)"
                >
                  Xóa
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>

      <!-- Empty State -->
      <div v-else class="table-empty-state">
        Chưa có dự án nào. Hãy tạo dự án mới để bắt đầu.
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '@/api/api'
import StatusBadge from '@/components/StatusBadge.vue'

const router = useRouter()

const projects = ref([])
const novelCounts = ref({})
const statuses = ref({})
const newProjectName = ref('')

// Fetch all projects
async function fetchProjects() {
  try {
    const data = await api.getProjects()
    projects.value = data || []
    
    // Fetch novel counts and statuses for each project
    await Promise.all(projects.value.map(async (proj) => {
      await Promise.all([
        fetchNovelCount(proj),
        fetchStatus(proj)
      ])
    }))
  } catch (err) {
    console.error('Failed to fetch projects:', err)
  }
}

// Fetch novel count for a project
async function fetchNovelCount(project) {
  try {
    const novels = await api.getNovels(project)
    novelCounts.value[project] = Array.isArray(novels) ? novels.length : 0
  } catch (err) {
    novelCounts.value[project] = 0
  }
}

// Fetch status for a project
async function fetchStatus(project) {
  try {
    statuses.value[project] = await api.getProjectStatus(project)
  } catch (err) {
    statuses.value[project] = null
  }
}

// Create a new project
async function createProject() {
  const name = newProjectName.value.trim()
  if (!name) return

  try {
    await api.createProject(name)
    newProjectName.value = ''
    await fetchProjects()
  } catch (err) {
    console.error('Failed to create project:', err)
    alert(err.message || 'Không thể tạo dự án!')
  }
}

// Delete a project with confirmation
async function confirmDelete(project) {
  if (!confirm(`Bạn có chắc muốn xóa dự án "${project}"? Thao tác này không thể hoàn tác.`)) {
    return
  }

  try {
    await api.deleteProject(project)
    await fetchProjects()
  } catch (err) {
    console.error('Failed to delete project:', err)
  }
}

onMounted(() => {
  fetchProjects()
})
</script>
