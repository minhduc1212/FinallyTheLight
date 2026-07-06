<template>
  <div class="novel-chunks-page">
    <!-- Top Nav / Back Button -->
    <div style="display: flex; gap: 16px; margin-bottom: 24px; align-items: center;">
      <button class="btn btn-outline" @click="$router.push(`/dashboard/${project}`)">
        Quay lại
      </button>
      <h3 style="font-size: 20px; font-weight: 600; margin: 0;">
        Dịch: <span style="font-family: var(--font-display); font-weight: 600;">{{ novel }}</span>
      </h3>
    </div>

    <!-- Action Bar & Configurations -->
    <div class="card" style="margin-bottom: 24px; padding: 24px;">
      <!-- Config Dropdowns Row -->
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; margin-bottom: 20px;">
        <!-- Genre Selector -->
        <div class="form-group" style="margin-bottom: 0;">
          <label class="form-label">Thể loại truyện</label>
          <select v-model="selectedGenre" class="form-input" style="padding: 8px 12px; height: 38px; width: 100%;">
            <option v-for="(g, key) in genres" :key="key" :value="key">
              {{ g.label }}
            </option>
          </select>
        </div>

        <!-- Source Language Selector -->
        <div class="form-group" style="margin-bottom: 0;">
          <label class="form-label">Ngôn ngữ nguồn</label>
          <select v-model="selectedSource" class="form-input" style="padding: 8px 12px; height: 38px; width: 100%;">
            <option value="auto">Tự động nhận diện</option>
            <option v-for="(lang, code) in languages" :key="code" :value="code">
              {{ lang.name }}
            </option>
          </select>
        </div>

        <!-- Target Language Selector -->
        <div class="form-group" style="margin-bottom: 0;">
          <label class="form-label">Ngôn ngữ đích</label>
          <select v-model="selectedTarget" class="form-input" style="padding: 8px 12px; height: 38px; width: 100%;">
            <option v-for="(lang, code) in languages" :key="code" :value="code">
              {{ lang.name }}
            </option>
          </select>
        </div>
      </div>

      <!-- Action Buttons Row -->
      <div style="display: flex; gap: 12px; justify-content: flex-end; flex-wrap: wrap; border-top: 1px solid var(--color-hairline); padding-top: 20px;">
        <button class="btn btn-outline" @click="showLogs = !showLogs" title="Xem nhật ký dịch thời gian thực">
          {{ showLogs ? 'Ẩn Nhật Ký' : 'Hiện Nhật Ký' }}
        </button>
        
        <button class="btn btn-outline" @click="downloadTranslation" :disabled="!status.output_file && !isDownloadAvailable" title="Tải file dịch hoàn chỉnh">
          Tải Bản Dịch
        </button>
        
        <template v-if="status.status === 'translating'">
          <button
            class="btn btn-danger"
            @click="cancelTranslation"
          >
            Tạm Dừng
          </button>
        </template>
        
        <template v-else>
          <button
            class="btn btn-outline"
            @click="translateSelected(true)"
            :disabled="selectedChunks.length === 0"
            title="Dịch các phân đoạn đã chọn"
          >
            Dịch Mục Chọn ({{ selectedChunks.length }})
          </button>
          
          <template v-if="hasCheckpoint">
            <button
              class="btn btn-filled"
              @click="translateAll(true)"
              title="Tiếp tục dịch từ phân đoạn cuối cùng"
            >
              Dịch Tiếp
            </button>
            <button
              class="btn btn-outline"
              @click="translateAll(false)"
              title="Dịch lại từ đầu, xóa tiến trình trước"
            >
              Dịch Mới
            </button>
          </template>
          
          <template v-else>
            <button
              class="btn btn-filled"
              @click="translateAll(false)"
            >
              Dịch Tất Cả
            </button>
          </template>
        </template>
      </div>
    </div>

    <!-- Progress Card (visible when translating) -->
    <div v-if="status.status === 'translating'" class="card progress-card" style="margin-bottom: 24px;">
      <div class="progress-info">
        <span style="font-weight: 600; color: var(--ink);">
          {{ status.step || 'Đang biên dịch...' }}
        </span>
        <span style="font-weight: 600; color: var(--slate);">
          Phân đoạn {{ status.current_chunk }} / {{ status.total_chunks }}
        </span>
      </div>
      <div class="progress-bar-track">
        <div class="progress-bar-fill" :style="{ width: progressPct + '%' }"></div>
      </div>
      <div style="text-align: right; font-size: 12px; color: var(--slate); margin-top: 6px; font-weight: 500;">
        {{ progressPct }}% hoàn thành
      </div>
    </div>

    <!-- Live Logs Terminal Panel -->
    <div v-if="showLogs" class="log-console-wrapper" style="margin-bottom: 24px;">
      <div style="display: flex; justify-content: space-between; align-items: center; background: #0c0d10; padding: 8px 16px; border-radius: 8px 8px 0 0; border-bottom: 1px solid #1f2026;">
        <span style="color: #a1a1aa; font-family: monospace; font-size: 12px; font-weight: 600;">TERMINAL LOGS</span>
        <button @click="status.logs = []" style="background: none; border: none; color: #a1a1aa; font-size: 11px; font-family: monospace; cursor: pointer; text-decoration: underline;">Xóa màn hình</button>
      </div>
      <div ref="logContainer" class="log-console" style="max-height: 250px; border-radius: 0 0 8px 8px; border-top: none;">
        <div v-for="(log, idx) in status.logs" :key="idx" :class="getLogLineClass(log)">
          {{ log }}
        </div>
        <div v-if="status.logs.length === 0" style="color: #52525b; font-style: italic;">Đang đợi log sự kiện...</div>
      </div>
    </div>

    <!-- Chunks Table Wrapper -->
    <div class="data-table-wrapper">
      <table class="data-table" v-if="chunks.length > 0">
        <thead>
          <tr>
            <th style="width: 40px; text-align: center;">
              <input type="checkbox" @change="toggleAll" :checked="isAllSelected" />
            </th>
            <th style="width: 60px;">ID</th>
            <th>Văn bản gốc</th>
            <th>Bản dịch</th>
            <th style="width: 140px;">Trạng thái</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="chunk in chunks" :key="chunk.id">
            <td style="text-align: center; vertical-align: top; padding-top: 14px;">
              <input type="checkbox" :value="chunk.id" v-model="selectedChunks" />
            </td>
            <td style="color: var(--stone); font-family: monospace; vertical-align: top; padding-top: 14px;">
              #{{ chunk.id + 1 }}
            </td>
            <td style="vertical-align: top;">
              <div class="chunk-text-box">{{ chunk.original }}</div>
            </td>
            <td style="vertical-align: top;">
              <div
                v-if="chunk.translated"
                class="chunk-text-box translated-text"
                v-html="formatMarkdown(chunk.translated)"
              ></div>
              <div v-else class="chunk-text-box placeholder-text">Chưa được dịch.</div>
            </td>
            <td style="vertical-align: top; padding-top: 14px;">
              <span :class="chunkStatusBadgeClass(chunk.status)">
                {{ chunkStatusLabel(chunk.status) }}
              </span>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-else class="empty-state" style="text-align: center; padding: 48px;">
        Đang nạp danh sách phân đoạn...
      </div>

      <!-- Pagination Footer -->
      <div class="pagination">
        <button class="btn btn-outline" :disabled="page <= 1" @click="changePage(page - 1)">
          Trang trước
        </button>
        <span style="color: var(--slate); font-weight: 500;">
          Trang {{ page }} / {{ totalPages }} ({{ totalChunks }} phân đoạn)
        </span>
        <button class="btn btn-outline" :disabled="page >= totalPages" @click="changePage(page + 1)">
          Trang sau
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { marked } from 'marked'

const route = useRoute()
const project = computed(() => route.params.project)
const novel = computed(() => route.params.novel)

// Genre & language selector config
const genres = ref({})
const languages = ref({})
const selectedGenre = ref('default')
const selectedSource = ref('auto')
const selectedTarget = ref('vi')

// Chunks list
const chunks = ref([])
const page = ref(1)
const limit = ref(50)
const totalChunks = ref(0)
const totalPages = ref(1)
const selectedChunks = ref([])

// Checkpoints
const checkpoints = ref([])

// Download availability check
const isDownloadAvailable = ref(false)

// Logs and translation status
const showLogs = ref(false)
const logContainer = ref(null)
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

// Progress percentage
const progressPct = computed(() => {
  const total = status.value.total_chunks || totalChunks.value
  if (!total) return 0
  return Math.round((status.value.current_chunk / total) * 100)
})

// Check if all chunks on the current page are selected
const isAllSelected = computed(() => {
  return chunks.value.length > 0 && chunks.value.every(c => selectedChunks.value.includes(c.id))
})

// Toggle all checkboxes on current page
function toggleAll(event) {
  if (event.target.checked) {
    chunks.value.forEach(c => {
      if (!selectedChunks.value.includes(c.id)) {
        selectedChunks.value.push(c.id)
      }
    })
  } else {
    chunks.value.forEach(c => {
      selectedChunks.value = selectedChunks.value.filter(id => id !== c.id)
    })
  }
}

// Load genres and languages
async function loadConfig() {
  try {
    const res = await fetch('/api/genres')
    if (res.ok) {
      const data = await res.json()
      genres.value = data.genres || {}
      languages.value = data.languages || {}
    }
  } catch (err) {
    console.error('Failed to load genres config:', err)
  }
}

// Load checkpoints list
async function loadCheckpoints() {
  if (!project.value) return
  try {
    const res = await fetch(`/api/projects/${project.value}/checkpoints`)
    if (res.ok) {
      checkpoints.value = await res.json()
    }
  } catch (err) {
    console.error('Failed to load checkpoints:', err)
  }
}

const hasCheckpoint = computed(() => {
  if (!novel.value || !checkpoints.value) return false
  const stem = novel.value.substring(0, novel.value.lastIndexOf('.')) || novel.value
  return checkpoints.value.some(cp => cp.file_stem === stem)
})

const expectedFilename = computed(() => {
  if (!novel.value) return ''
  const dotIdx = novel.value.lastIndexOf('.')
  const stem = dotIdx !== -1 ? novel.value.substring(0, dotIdx) : novel.value
  const ext = dotIdx !== -1 ? novel.value.substring(dotIdx) : '.txt'
  return `${stem}_${selectedTarget.value}${ext}`
})

async function checkDownloadAvailable() {
  if (!expectedFilename.value || !project.value) {
    isDownloadAvailable.value = false
    return
  }
  try {
    const res = await fetch(`/api/projects/${project.value}/download/${encodeURIComponent(expectedFilename.value)}`, { method: 'HEAD' })
    isDownloadAvailable.value = res.ok
  } catch (e) {
    isDownloadAvailable.value = false
  }
}

// Load chunks for current novel
async function loadChunks() {
  if (!project.value || !novel.value) return
  try {
    const res = await fetch(`/api/projects/${project.value}/novels/${encodeURIComponent(novel.value)}/chunks?page=${page.value}&limit=${limit.value}`)
    if (res.ok) {
      const data = await res.json()
      chunks.value = data.chunks || []
      totalChunks.value = data.total_chunks || 0
      totalPages.value = Math.ceil(totalChunks.value / limit.value) || 1
    }
  } catch (err) {
    console.error('Failed to load chunks:', err)
  }
}

// Page navigation
function changePage(p) {
  if (p < 1 || p > totalPages.value) return
  page.value = p
  loadChunks()
}

// Format status badge CSS
function chunkStatusBadgeClass(st) {
  switch (st) {
    case 'completed': return 'badge badge-completed'
    case 'failed': return 'badge badge-failed'
    case 'translating': return 'badge badge-translating'
    default: return 'badge badge-pending'
  }
}

// Format status label text
function chunkStatusLabel(st) {
  switch (st) {
    case 'completed': return 'Đã dịch'
    case 'failed': return 'Lỗi dịch'
    case 'translating': return 'Đang xử lý'
    default: return 'Chờ dịch'
  }
}

// Parse markdown to HTML safe
function formatMarkdown(text) {
  if (!text) return ''
  try {
    return marked.parse(text)
  } catch (e) {
    return text
  }
}

// Start polling status
function startPolling() {
  if (pollInterval) clearInterval(pollInterval)
  pollInterval = setInterval(async () => {
    try {
      const res = await fetch(`/api/projects/${project.value}/status`)
      if (res.ok) {
        const data = await res.json()
        status.value = data

        if (showLogs.value) {
          await nextTick()
          if (logContainer.value) {
            logContainer.value.scrollTop = logContainer.value.scrollHeight
          }
        }

        if (data.status === 'completed' || data.status === 'failed' || data.status === 'idle') {
          clearInterval(pollInterval)
          pollInterval = null
          await loadChunks()
          await loadCheckpoints()
          await checkDownloadAvailable()
        }
      }
    } catch (err) {
      console.error('Polling error:', err)
    }
  }, 2000)
}

// Start custom translation task for selected chunks
async function translateSelected(resume = true) {
  if (selectedChunks.value.length === 0) return
  try {
    const res = await fetch(`/api/projects/${project.value}/novels/${encodeURIComponent(novel.value)}/translate_chunks`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        target_chunks: selectedChunks.value,
        genre: selectedGenre.value,
        source_lang: selectedSource.value,
        target_lang: selectedTarget.value,
        resume: resume
      })
    })
    if (res.ok) {
      showLogs.value = true
      selectedChunks.value = []
      startPolling()
    }
  } catch (err) {
    console.error('Failed to translate selected chunks:', err)
  }
}

// Start translation task for all chunks
async function translateAll(resume = true) {
  if (!resume && !confirm("Bạn có chắc chắn muốn dịch lại tiểu thuyết này từ đầu? Mọi tiến trình đã lưu sẽ bị ghi đè.")) {
    return
  }
  try {
    const res = await fetch(`/api/projects/${project.value}/novels/${encodeURIComponent(novel.value)}/translate_chunks`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        target_chunks: null,
        genre: selectedGenre.value,
        source_lang: selectedSource.value,
        target_lang: selectedTarget.value,
        resume: resume
      })
    })
    if (res.ok) {
      showLogs.value = true
      startPolling()
    }
  } catch (err) {
    console.error('Failed to translate all chunks:', err)
  }
}

// Cancel translation task (Pause)
async function cancelTranslation() {
  try {
    const res = await fetch(`/api/projects/${project.value}/cancel`, { method: 'POST' })
    if (res.ok) {
      setTimeout(async () => {
        await loadChunks()
        await loadCheckpoints()
      }, 1000)
    }
  } catch (err) {
    console.error('Failed to cancel translation:', err)
  }
}

// Download translation output file
function downloadTranslation() {
  const fileToDownload = status.value.output_file || expectedFilename.value
  if (!fileToDownload) return
  window.open(`/api/projects/${project.value}/download/${encodeURIComponent(fileToDownload)}`, '_blank')
}

// Styling for different kinds of logs
function getLogLineClass(log) {
  if (log.includes('LỖI') || log.includes('Failed') || log.includes('error')) return 'log-line-error'
  if (log.includes('completed') || log.includes('Done') || log.includes('Success')) return 'log-line-success'
  return ''
}

// Watchers
watch([project, novel], () => {
  page.value = 1
  selectedChunks.value = []
  loadChunks()
  loadCheckpoints()
  checkDownloadAvailable()
})

watch(selectedTarget, () => {
  checkDownloadAvailable()
})

onMounted(async () => {
  await loadConfig()
  await loadChunks()
  await loadCheckpoints()
  await checkDownloadAvailable()
  
  // Fetch current status to see if already translating
  fetch(`/api/projects/${project.value}/status`)
    .then(res => res.json())
    .then(data => {
      status.value = data
      if (data.status === 'translating') {
        showLogs.value = true
        startPolling()
      }
    })
})

onUnmounted(() => {
  if (pollInterval) clearInterval(pollInterval)
})
</script>

<style scoped>
.action-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
  align-items: flex-end;
}

@media (min-width: 900px) {
  .btn-group {
    grid-column: span 2;
  }
}

.chunk-text-box {
  max-height: 140px;
  overflow-y: auto;
  font-size: 14px;
  line-height: 1.6;
  color: var(--ink);
  white-space: pre-wrap;
  padding-right: 8px;
}

.placeholder-text {
  color: var(--stone);
  font-style: italic;
}

.translated-text :deep(p) {
  margin-bottom: 8px;
}
.translated-text :deep(p:last-child) {
  margin-bottom: 0;
}

.log-console-wrapper {
  box-shadow: var(--shadow-xs);
}
</style>
