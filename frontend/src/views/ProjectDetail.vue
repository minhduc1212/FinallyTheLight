<template>
  <div>
    <!-- Header -->
    <div class="page-header">
      <div>
        <h2>Tiểu thuyết <span class="subtitle">— {{ project }}</span></h2>
      </div>
      <div>
        <button class="btn btn-filled" @click="$refs.fileInput.click()">
          Tải lên tiểu thuyết
        </button>
        <input
          ref="fileInput"
          type="file"
          class="hidden-file-input"
          accept=".txt,.md"
          @change="handleUpload"
        />
      </div>
    </div>

    <!-- Translation Progress -->
    <div v-if="status.status === 'translating'" class="card progress-card">
      <div class="progress-info">
        <span>{{ status.step || 'Đang dịch...' }}</span>
        <span>Chunk {{ status.current_chunk }} / {{ status.total_chunks }}</span>
      </div>
      <div class="progress-bar-track">
        <div class="progress-bar-fill" :style="{ width: progressPct + '%' }"></div>
      </div>
      <div style="text-align: right; font-size: 12px; color: var(--color-slate); margin-top: 6px;">
        {{ progressPct }}%
      </div>
    </div>

    <!-- Novel Table -->
    <div class="data-table-wrapper">
      <table class="data-table" v-if="novels.length > 0">
        <thead>
          <tr>
            <th style="width: 50px;">#</th>
            <th>Tên file</th>
            <th style="width: 200px;">Hành động</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(name, idx) in novels" :key="name">
            <td>{{ idx + 1 }}</td>
            <td>
              <router-link
                :to="`/dashboard/${project}/novels/${encodeURIComponent(name)}`"
                class="novel-link"
              >
                {{ name }}
              </router-link>
            </td>
            <td>
              <div class="actions-cell">
                <button
                  class="btn btn-outline"
                  @click="$router.push(`/dashboard/${project}/novels/${encodeURIComponent(name)}`)"
                >
                  Dịch
                </button>
                <button class="btn btn-danger" @click="deleteNovel(name)">
                  Xóa
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-else class="empty-state">
        Chưa có tiểu thuyết nào. Hãy tải lên file .txt hoặc .md
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()
const project = computed(() => route.params.project)

const novels = ref([])
const status = ref({ status: 'idle', current_chunk: 0, total_chunks: 0, step: '', logs: [], error: null, output_file: null })

let pollInterval = null

const progressPct = computed(() => {
  if (!status.value.total_chunks) return 0
  return Math.round((status.value.current_chunk / status.value.total_chunks) * 100)
})

async function loadNovels() {
  try {
    const res = await fetch(`/api/projects/${project.value}/novels`)
    if (res.ok) {
      novels.value = await res.json()
    }
  } catch (e) {
    console.error('Failed to load novels:', e)
  }
}

async function loadStatus() {
  try {
    const res = await fetch(`/api/projects/${project.value}/status`)
    if (res.ok) {
      status.value = await res.json()
      if (status.value.status === 'translating') {
        startPolling()
      } else {
        stopPolling()
      }
    }
  } catch (e) {
    console.error('Failed to load status:', e)
  }
}

function startPolling() {
  if (pollInterval) return
  pollInterval = setInterval(async () => {
    try {
      const res = await fetch(`/api/projects/${project.value}/status`)
      if (res.ok) {
        status.value = await res.json()
        if (status.value.status !== 'translating') {
          stopPolling()
        }
      }
    } catch (e) {
      console.error('Polling failed:', e)
    }
  }, 2000)
}

function stopPolling() {
  if (pollInterval) {
    clearInterval(pollInterval)
    pollInterval = null
  }
}

async function handleUpload(event) {
  const file = event.target.files[0]
  if (!file) return
  const formData = new FormData()
  formData.append('file', file)
  try {
    await fetch(`/api/projects/${project.value}/novels`, {
      method: 'POST',
      body: formData
    })
    await loadNovels()
  } catch (e) {
    console.error('Upload failed:', e)
  }
  event.target.value = ''
}

async function deleteNovel(name) {
  if (!confirm(`Xóa tiểu thuyết "${name}"?`)) return
  try {
    await fetch(`/api/projects/${project.value}/novels/${encodeURIComponent(name)}`, {
      method: 'DELETE'
    })
    await loadNovels()
  } catch (e) {
    console.error('Delete failed:', e)
  }
}

onMounted(() => {
  loadNovels()
  loadStatus()
})

onUnmounted(() => {
  stopPolling()
})
</script>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.page-header h2 {
  font-size: 24px;
  font-weight: 600;
  margin: 0;
}

.subtitle {
  font-size: 18px;
  color: var(--color-slate);
  font-weight: 400;
}

.data-table-wrapper {
  background: var(--color-paper);
  border: 1px solid var(--color-hairline);
  border-radius: var(--radius-cards);
  overflow: hidden;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}

.data-table th {
  text-align: left;
  padding: 12px 16px;
  font-weight: 600;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--color-slate);
  border-bottom: 1px solid var(--color-hairline);
  background: var(--color-mist);
}

.data-table td {
  padding: 12px 16px;
  border-bottom: 1px solid var(--color-hairline);
  vertical-align: middle;
}

.data-table tr:last-child td {
  border-bottom: none;
}

.data-table tr:hover td {
  background: var(--color-bone);
}

.actions-cell {
  display: flex;
  gap: 8px;
}

.novel-link {
  color: var(--color-ink);
  text-decoration: none;
  font-weight: 500;
}

.novel-link:hover {
  color: var(--color-seal-red);
}

.card {
  background: var(--color-paper);
  border: 1px solid var(--color-hairline);
  border-radius: var(--radius-cards);
  padding: 24px;
}

.progress-card {
  margin-bottom: 24px;
}

.progress-info {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
  font-size: 13px;
  font-weight: 500;
}

.empty-state {
  text-align: center;
  padding: 48px 32px;
  color: var(--color-stone);
  font-size: 14px;
}
</style>
