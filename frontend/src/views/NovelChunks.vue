<template>
  <div class="novel-chunks-page">
    <!-- Top Nav / Back Button -->
    <div style="display: flex; gap: 16px; margin-bottom: 24px; align-items: center;">
      <button class="btn btn-outline" @click="router.push(`/dashboard/${project}`)">
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
            Hủy dịch
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

    <!-- Progress Card (visible when translating, completed or failed) -->
    <div v-if="status.status === 'translating' || status.status === 'completed' || status.status === 'failed'" class="card progress-card" style="margin-bottom: 24px;">
      <div class="progress-info">
        <span style="font-weight: 600; color: var(--ink); display: flex; align-items: center; gap: 8px;">
          {{ status.step || 'Đang biên dịch...' }}
          <StatusBadge :status="status.status" type="project" />
        </span>
        <span style="font-weight: 600; color: var(--slate);">
          Phân đoạn {{ status.current_chunk }} / {{ status.total_chunks }}
        </span>
      </div>
      <div class="progress-bar-track">
        <div class="progress-bar-fill" :style="{ width: progressPct + '%' }"></div>
      </div>
      <div style="display: flex; justify-content: space-between; font-size: 12px; color: var(--slate); margin-top: 6px; font-weight: 500;">
        <span>Thời gian chạy: {{ formatDuration(status.elapsed_time) }}</span>
        <span>{{ progressPct }}% hoàn thành</span>
      </div>
      
      <!-- Target chunks indicator if only translating selected chunks -->
      <div v-if="status.target_chunks && status.target_chunks.length > 0" style="font-size: 12px; color: var(--color-slate); margin-top: 8px; padding-top: 8px; border-top: 1px dotted var(--color-hairline);">
        <span style="font-weight: 600; color: var(--ink);">Mục tiêu dịch:</span> 
        Các phân đoạn {{ status.target_chunks.map(i => '#' + (i + 1)).join(', ') }}
      </div>

      <!-- Card Action Buttons -->
      <div style="display: flex; gap: 8px; margin-top: 12px; padding-top: 10px; border-top: 1px dashed var(--color-hairline); justify-content: flex-end;">
        <button
          v-if="status.status === 'translating'"
          class="btn btn-danger"
          style="padding: 6px 14px; font-size: 13px;"
          @click="cancelTranslation"
        >
          Hủy dịch
        </button>
        <button
          v-if="status.status === 'failed' && hasCheckpoint"
          class="btn btn-filled"
          style="padding: 6px 14px; font-size: 13px;"
          @click="translateAll(true)"
        >
          Tiếp tục dịch
        </button>
      </div>
    </div>

    <!-- Live Logs Terminal Panel -->
    <LogConsole 
      v-if="showLogs" 
      :logs="status.logs" 
      @clear="status.logs = []" 
    />

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
            <th style="width: 160px;">Trạng thái</th>
            <th style="width: 100px;">Hành động</th>
          </tr>
        </thead>
        <tbody>
          <tr 
            v-for="chunk in chunks" 
            :key="chunk.id"
            :class="{ 'target-chunk-highlight': status.target_chunks && status.target_chunks.includes(chunk.id) }"
          >
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
              <StatusBadge :status="getChunkStatus(chunk)" type="chunk" />
              <!-- Detailed metadata if present or currently translating -->
              <div v-if="chunk.meta || getChunkStatus(chunk) === 'translating'" style="font-size: 11px; color: var(--color-slate); margin-top: 6px; line-height: 1.4;">
                <div v-if="getChunkStatus(chunk) === 'translating'">
                  Lượt thử: {{ status.try_count || 1 }}
                </div>
                <div v-else>
                  <div v-if="chunk.meta.try_count">Lượt thử: {{ chunk.meta.try_count }}</div>
                  <div v-if="chunk.meta.elapsed_time">Thời gian: {{ chunk.meta.elapsed_time }}s</div>
                  <div v-if="chunk.meta.error" style="color: var(--color-seal-red); cursor: help;" :title="chunk.meta.error">
                    Lỗi: {{ chunk.meta.error.length > 30 ? chunk.meta.error.substring(0, 30) + '...' : chunk.meta.error }}
                  </div>
                </div>
              </div>
            </td>
            <td style="vertical-align: top; padding-top: 10px;">
              <button 
                class="btn btn-outline" 
                style="padding: 4px 8px; font-size: 12px; height: 26px;" 
                @click="retranslateChunk(chunk.id)"
                :disabled="status.status === 'translating'"
                title="Dịch lại phân đoạn này"
              >
                Dịch lại
              </button>
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
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { marked } from 'marked'
import { api } from '@/api/api'
import StatusBadge from '@/components/StatusBadge.vue'
import LogConsole from '@/components/LogConsole.vue'

const route = useRoute()
const router = useRouter()
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
    const data = await api.getGenresConfig()
    genres.value = data.genres || {}
    languages.value = data.languages || {}
  } catch (err) {
    console.error('Failed to load genres config:', err)
  }
}

// Load checkpoints list
async function loadCheckpoints() {
  if (!project.value) return
  try {
    checkpoints.value = await api.getCheckpoints(project.value)
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
    isDownloadAvailable.value = await api.checkDownloadAvailable(project.value, expectedFilename.value)
  } catch (e) {
    isDownloadAvailable.value = false
  }
}

// Load chunks for current novel
async function loadChunks() {
  if (!project.value || !novel.value) return
  try {
    const data = await api.getNovelChunks(project.value, novel.value, page.value, limit.value)
    chunks.value = data.chunks || []
    totalChunks.value = data.total_chunks || 0
    totalPages.value = Math.ceil(totalChunks.value / limit.value) || 1
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

// Parse markdown to HTML safe
function formatMarkdown(text) {
  if (!text) return ''
  try {
    return marked.parse(text)
  } catch (e) {
    return text
  }
}

function getChunkStatus(chunk) {
  if (status.value.status === 'translating') {
    if (chunk.id === status.value.current_chunk - 1) {
      return 'translating'
    }
  }
  return chunk.status
}

// Start polling status
let lastCurrentChunk = 0
function startPolling() {
  if (pollInterval) clearInterval(pollInterval)
  lastCurrentChunk = status.value.current_chunk
  pollInterval = setInterval(async () => {
    try {
      const data = await api.getProjectStatus(project.value)
      status.value = data

      // If chunk changed, reload chunks to show newly completed translations
      if (data.current_chunk !== lastCurrentChunk) {
        lastCurrentChunk = data.current_chunk
        await loadChunks()
      }

      if (data.status === 'completed' || data.status === 'failed' || data.status === 'idle') {
        clearInterval(pollInterval)
        pollInterval = null
        await loadChunks()
        await loadCheckpoints()
        await checkDownloadAvailable()
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
    status.value = {
      ...status.value,
      status: 'translating',
      logs: ['[SYS ] Đang kết nối và khởi động tiến trình dịch...'],
      target_chunks: [...selectedChunks.value],
      current_chunk: 0,
      total_chunks: selectedChunks.value.length
    }
    await api.translateChunks(project.value, novel.value, {
      target_chunks: selectedChunks.value,
      genre: selectedGenre.value,
      source_lang: selectedSource.value,
      target_lang: selectedTarget.value,
      resume
    })
    showLogs.value = true
    selectedChunks.value = []
    startPolling()
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
    status.value = {
      ...status.value,
      status: 'translating',
      logs: ['[SYS ] Đang kết nối và khởi động tiến trình dịch...'],
      target_chunks: null,
      current_chunk: 0,
      total_chunks: totalChunks.value
    }
    await api.translateChunks(project.value, novel.value, {
      target_chunks: null,
      genre: selectedGenre.value,
      source_lang: selectedSource.value,
      target_lang: selectedTarget.value,
      resume
    })
    showLogs.value = true
    startPolling()
  } catch (err) {
    console.error('Failed to translate all chunks:', err)
  }
}

// Cancel translation task (Pause)
async function cancelTranslation() {
  try {
    status.value.status = 'failed'
    status.value.step = 'Đã hủy'
    await api.cancelTranslation(project.value)
    await loadChunks()
    await loadCheckpoints()
  } catch (err) {
    console.error('Failed to cancel translation:', err)
  }
}

// Download translation output file
function downloadTranslation() {
  const fileToDownload = status.value.output_file || expectedFilename.value
  if (!fileToDownload) return
  const url = api.getDownloadUrl(project.value, fileToDownload)
  window.open(url, '_blank')
}

async function retranslateChunk(chunkId) {
  if (!confirm(`Bạn có chắc chắn muốn dịch lại phân đoạn #${chunkId + 1}? Tiến trình cũ của phân đoạn này sẽ bị ghi đè.`)) {
    return
  }
  try {
    status.value = {
      ...status.value,
      status: 'translating',
      logs: ['[SYS ] Đang kết nối và khởi động tiến trình dịch...'],
      target_chunks: [chunkId],
      current_chunk: 0,
      total_chunks: 1
    }
    await api.translateChunks(project.value, novel.value, {
      target_chunks: [chunkId],
      genre: selectedGenre.value,
      source_lang: selectedSource.value,
      target_lang: selectedTarget.value,
      resume: false // Force retranslation of this specific chunk
    })
    showLogs.value = true
    startPolling()
  } catch (err) {
    console.error('Failed to retranslate chunk:', err)
  }
}

function formatDuration(seconds) {
  if (!seconds) return '0s'
  if (seconds < 60) return `${Math.round(seconds)}s`
  const mins = Math.floor(seconds / 60)
  const secs = Math.round(seconds % 60)
  return `${mins}m ${secs}s`
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
  try {
    const data = await api.getProjectStatus(project.value)
    status.value = data
    if (data.status === 'translating') {
      showLogs.value = true
      startPolling()
    }
  } catch (err) {
    console.error('Failed to get initialization status:', err)
  }
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
.target-chunk-highlight {
  background-color: rgba(96, 165, 250, 0.08) !important;
  border-left: 4px solid var(--color-blue);
}
</style>
