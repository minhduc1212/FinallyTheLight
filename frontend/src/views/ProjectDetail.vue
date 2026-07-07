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
    <div v-if="status.status === 'translating' || (status.status === 'failed' && hasCheckpoint)" class="card progress-card" style="margin-bottom: 24px;">
      <div class="progress-info">
        <span style="font-weight: 600; color: var(--color-ink); display: flex; align-items: center; gap: 8px;">
          {{ status.step || 'Đang dịch...' }}
          <StatusBadge :status="status.status" type="project" />
        </span>
        <span>Chunk {{ status.current_chunk }} / {{ status.total_chunks }}</span>
      </div>
      <div class="progress-bar-track">
        <div class="progress-bar-fill" :style="{ width: progressPct + '%' }"></div>
      </div>
      <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 6px;">
        <span style="font-size: 12px; color: var(--color-slate); font-weight: 500;">
          Thời gian chạy: {{ formatDuration(status.elapsed_time) }} ({{ progressPct }}%)
        </span>
        <div style="display: flex; gap: 8px;">
          <button
            v-if="status.status === 'translating'"
            class="btn btn-danger"
            style="padding: 4px 10px; font-size: 12px; height: 26px;"
            @click="cancelTranslation"
          >
            Hủy dịch
          </button>
          <button
            v-if="status.status === 'failed' && hasCheckpoint"
            class="btn btn-filled"
            style="padding: 4px 10px; font-size: 12px; height: 26px;"
            @click="resumeTranslation"
          >
            Tiếp tục dịch
          </button>
        </div>
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
                  @click="router.push(`/dashboard/${project}/novels/${encodeURIComponent(name)}`)"
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
import { api } from '@/api/api'
import StatusBadge from '@/components/StatusBadge.vue'

const route = useRoute()
const router = useRouter()
const project = computed(() => route.params.project)

const novels = ref([])
const status = ref({
  status: 'idle',
  current_chunk: 0,
  total_chunks: 0,
  step: '',
  logs: [],
  error: null,
  output_file: null
})

let pollInterval = null

const progressPct = computed(() => {
  if (!status.value.total_chunks) return 0
  return Math.round((status.value.current_chunk / status.value.total_chunks) * 100)
})

const checkpoints = ref([])

async function loadCheckpoints() {
  try {
    checkpoints.value = await api.getCheckpoints(project.value)
  } catch (e) {
    console.error('Failed to load checkpoints:', e)
  }
}

const hasCheckpoint = computed(() => {
  return checkpoints.value.length > 0
})

async function cancelTranslation() {
  try {
    await api.cancelTranslation(project.value)
    setTimeout(async () => {
      await loadStatus()
      await loadCheckpoints()
    }, 1000)
  } catch (e) {
    console.error('Failed to cancel translation:', e)
  }
}

async function resumeTranslation() {
  await loadCheckpoints()
  if (checkpoints.value.length === 0) return
  
  // Find the novel corresponding to the checkpoint stem
  const stem = checkpoints.value[0].file_stem
  const matchingNovel = novels.value.find(n => {
    const dotIdx = n.lastIndexOf('.')
    const nameWithoutExt = dotIdx !== -1 ? n.substring(0, dotIdx) : n
    return nameWithoutExt === stem
  })
  
  if (!matchingNovel) {
    alert('Không tìm thấy file tiểu thuyết tương ứng cho tiến trình này!')
    return
  }
  
  try {
    await api.translateChunks(project.value, matchingNovel, {
      target_chunks: null,
      genre: 'default',
      source_lang: 'auto',
      target_lang: 'vi',
      resume: true // Keep true to resume from checkpoint!
    })
    await loadStatus()
  } catch (e) {
    console.error('Failed to resume translation:', e)
  }
}

function formatDuration(seconds) {
  if (!seconds) return '0s'
  if (seconds < 60) return `${Math.round(seconds)}s`
  const mins = Math.floor(seconds / 60)
  const secs = Math.round(seconds % 60)
  return `${mins}m ${secs}s`
}

async function loadNovels() {
  try {
    novels.value = await api.getNovels(project.value)
  } catch (e) {
    console.error('Failed to load novels:', e)
  }
}

async function loadStatus() {
  try {
    status.value = await api.getProjectStatus(project.value)
    if (status.value.status === 'translating') {
      startPolling()
    } else {
      stopPolling()
    }
  } catch (e) {
    console.error('Failed to load status:', e)
  }
}

function startPolling() {
  if (pollInterval) return
  pollInterval = setInterval(async () => {
    try {
      status.value = await api.getProjectStatus(project.value)
      if (status.value.status !== 'translating') {
        stopPolling()
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
  try {
    await api.uploadNovel(project.value, file)
    await loadNovels()
  } catch (e) {
    console.error('Upload failed:', e)
  }
  event.target.value = ''
}

async function deleteNovel(name) {
  if (!confirm(`Xóa tiểu thuyết "${name}"?`)) return
  try {
    await api.deleteNovel(project.value, name)
    await loadNovels()
  } catch (e) {
    console.error('Delete failed:', e)
  }
}

onMounted(() => {
  loadNovels()
  loadStatus()
  loadCheckpoints()
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
