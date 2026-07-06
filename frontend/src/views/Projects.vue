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
              <span :class="statusBadgeClass(project)">
                {{ statusLabel(project) }}
              </span>
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

const router = useRouter()

const projects = ref([])
const novelCounts = ref({})
const statuses = ref({})
const newProjectName = ref('')

// Fetch all projects
async function fetchProjects() {
  try {
    const res = await fetch('/api/projects')
    if (res.ok) {
      projects.value = await res.json()
      // Fetch novel counts and statuses for each project
      await Promise.all(projects.value.map(async (proj) => {
        await Promise.all([
          fetchNovelCount(proj),
          fetchStatus(proj)
        ])
      }))
    }
  } catch (err) {
    console.error('Failed to fetch projects:', err)
  }
}

// Fetch novel count for a project
async function fetchNovelCount(project) {
  try {
    const res = await fetch(`/api/projects/${encodeURIComponent(project)}/novels`)
    if (res.ok) {
      const novels = await res.json()
      novelCounts.value[project] = Array.isArray(novels) ? novels.length : 0
    }
  } catch (err) {
    novelCounts.value[project] = 0
  }
}

// Fetch status for a project
async function fetchStatus(project) {
  try {
    const res = await fetch(`/api/projects/${encodeURIComponent(project)}/status`)
    if (res.ok) {
      statuses.value[project] = await res.json()
    }
  } catch (err) {
    statuses.value[project] = null
  }
}

// Get status badge class
function statusBadgeClass(project) {
  const status = statuses.value[project]
  if (!status || !status.status) return 'badge badge-pending'
  
  switch (status.status) {
    case 'running':
    case 'translating':
      return 'badge badge-translating'
    case 'error':
    case 'failed':
      return 'badge badge-failed'
    case 'completed':
    case 'done':
      return 'badge badge-completed'
    default:
      return 'badge badge-pending'
  }
}

// Get status label
function statusLabel(project) {
  const status = statuses.value[project]
  if (!status || !status.status) return 'Rảnh'
  
  switch (status.status) {
    case 'running':
    case 'translating':
      return 'Đang dịch'
    case 'error':
    case 'failed':
      return 'Lỗi'
    case 'completed':
    case 'done':
      return 'Hoàn tất'
    default:
      return 'Rảnh'
  }
}

// Create a new project
async function createProject() {
  const name = newProjectName.value.trim()
  if (!name) return

  try {
    const res = await fetch(`/api/projects/${encodeURIComponent(name)}`, {
      method: 'POST'
    })
    if (res.ok) {
      newProjectName.value = ''
      await fetchProjects()
    } else {
      const data = await res.json()
      alert(data.detail || 'Không thể tạo dự án!')
    }
  } catch (err) {
    console.error('Failed to create project:', err)
    alert('Lỗi kết nối khi tạo dự án!')
  }
}

// Delete a project with confirmation
async function confirmDelete(project) {
  if (!confirm(`Bạn có chắc muốn xóa dự án "${project}"? Thao tác này không thể hoàn tác.`)) {
    return
  }

  try {
    const res = await fetch(`/api/projects/${encodeURIComponent(project)}`, {
      method: 'DELETE'
    })
    if (res.ok) {
      await fetchProjects()
    }
  } catch (err) {
    console.error('Failed to delete project:', err)
  }
}

onMounted(() => {
  fetchProjects()
})
</script>
