<template>
  <div class="settings-page">
    <div class="page-header">
      <h2>Thiết lập Toàn cục</h2>
    </div>

    <div v-if="settings" class="card" style="padding: 0; overflow: hidden;">
      <!-- Tab Navigation -->
      <div class="tab-bar">
        <button
          v-for="tab in tabs"
          :key="tab.id"
          class="tab-item"
          :class="{ active: activeTab === tab.id }"
          @click="activeTab = tab.id"
        >
          {{ tab.name }}
        </button>
      </div>

      <!-- Tab Content -->
      <div style="padding: 24px;">
        <!-- Tab 1: Model -->
        <div v-if="activeTab === 'model'" class="form-container">
          <div class="form-group">
            <label class="form-label">Tên Model (LLM)</label>
            <input
              v-model="settings.model.name"
              type="text"
              class="form-input"
              placeholder="Ví dụ: gemma-4-31b-it"
            />
          </div>
          <div class="form-group">
            <label class="form-label">Temperature</label>
            <input
              v-model.number="settings.model.temperature"
              type="number"
              step="0.05"
              min="0"
              max="2"
              class="form-input"
            />
          </div>
          <div class="form-group">
            <label class="form-label">Top P</label>
            <input
              v-model.number="settings.model.top_p"
              type="number"
              step="0.05"
              min="0"
              max="1"
              class="form-input"
            />
          </div>
        </div>

        <!-- Tab 2: Translation -->
        <div v-if="activeTab === 'translation'" class="form-container">
          <div class="form-group">
            <label class="form-label">Kích thước Chunk (Ký tự)</label>
            <input
              v-model.number="settings.translation.chunk_size"
              type="number"
              class="form-input"
            />
          </div>
          <div class="form-group">
            <label class="form-label">Số luồng tối đa (Max Workers)</label>
            <input
              v-model.number="settings.translation.max_workers"
              type="number"
              class="form-input"
            />
          </div>
          <div class="form-group">
            <label class="form-label">Thể loại mặc định</label>
            <input
              v-model="settings.translation.genre"
              type="text"
              class="form-input"
            />
          </div>
          <div class="form-group">
            <label class="form-label">Ngôn ngữ đích mặc định</label>
            <input
              v-model="settings.translation.target_language"
              type="text"
              class="form-input"
            />
          </div>
          <div class="form-group">
            <label class="form-label">Ngưỡng trùng lặp (Cosine Similarity)</label>
            <input
              v-model.number="settings.translation.duplicate_threshold"
              type="number"
              step="0.05"
              class="form-input"
            />
          </div>
          <div class="form-group">
            <label class="form-label">Ngưỡng lười dịch (Lazy Threshold)</label>
            <input
              v-model.number="settings.translation.lazy_threshold"
              type="number"
              step="0.05"
              class="form-input"
            />
          </div>
          <div class="form-group">
            <label class="form-label">Similarity Lookback (Số chunk xem lại)</label>
            <input
              v-model.number="settings.translation.similarity_lookback"
              type="number"
              class="form-input"
            />
          </div>
          <div class="form-group">
            <label class="form-label">Lịch sử chương (Chapters Lookback)</label>
            <input
              v-model.number="settings.translation.history_chapters"
              type="number"
              class="form-input"
            />
          </div>
          <div class="form-group">
            <label class="form-label">Token Budget lịch sử</label>
            <input
              v-model.number="settings.translation.history_token_budget"
              type="number"
              class="form-input"
            />
          </div>
        </div>

        <!-- Tab 3: Features -->
        <div v-if="activeTab === 'features'" class="form-container grid-checkboxes">
          <div class="form-checkbox-group">
            <input
              id="auto_glossary"
              v-model="settings.features.auto_glossary"
              type="checkbox"
            />
            <label for="auto_glossary" class="form-label" style="margin-bottom: 0;">Tự động trích xuất Thuật ngữ</label>
          </div>
          <div class="form-checkbox-group">
            <input
              id="auto_summary"
              v-model="settings.features.auto_summary"
              type="checkbox"
            />
            <label for="auto_summary" class="form-label" style="margin-bottom: 0;">Tự động tóm tắt ngữ cảnh</label>
          </div>
          <div class="form-checkbox-group">
            <input
              id="clean_thinking"
              v-model="settings.features.clean_thinking_tags"
              type="checkbox"
            />
            <label for="clean_thinking" class="form-label" style="margin-bottom: 0;">Xóa thẻ suy nghĩ của model</label>
          </div>
          <div class="form-checkbox-group">
            <input
              id="detect_duplicate"
              v-model="settings.features.detect_duplicate_translation"
              type="checkbox"
            />
            <label for="detect_duplicate" class="form-label" style="margin-bottom: 0;">Phát hiện bản dịch trùng lặp</label>
          </div>
          <div class="form-checkbox-group">
            <input
              id="editing_and_proof"
              v-model="settings.features.editing_and_proofreading"
              type="checkbox"
            />
            <label for="editing_and_proof" class="form-label" style="margin-bottom: 0;">Hiệu đính & Đánh bóng (lượt 2)</label>
          </div>
          <div class="form-checkbox-group">
            <input
              id="inject_glossary"
              v-model="settings.features.inject_glossary_in_system_prompt"
              type="checkbox"
            />
            <label for="inject_glossary" class="form-label" style="margin-bottom: 0;">Tiêm glossary vào System Prompt</label>
          </div>
          <div class="form-checkbox-group">
            <input
              id="relevance_filter"
              v-model="settings.features.relevance_filtering"
              type="checkbox"
            />
            <label for="relevance_filter" class="form-label" style="margin-bottom: 0;">Lọc thuật ngữ liên quan</label>
          </div>
          <div class="form-checkbox-group">
            <input
              id="rolling_history"
              v-model="settings.features.rolling_history"
              type="checkbox"
            />
            <label for="rolling_history" class="form-label" style="margin-bottom: 0;">Dịch tuần tự với lịch sử cuộn</label>
          </div>
          <div class="form-checkbox-group">
            <input
              id="summary_history"
              v-model="settings.features.summary_history"
              type="checkbox"
            />
            <label for="summary_history" class="form-label" style="margin-bottom: 0;">Lịch sử tóm tắt</label>
          </div>
          <div class="form-checkbox-group">
            <input
              id="use_async"
              v-model="settings.features.use_async_client"
              type="checkbox"
            />
            <label for="use_async" class="form-label" style="margin-bottom: 0;">Client bất đồng bộ</label>
          </div>
        </div>

        <!-- Tab 4: Concurrency -->
        <div v-if="activeTab === 'concurrency'" class="form-container">
          <div class="form-group">
            <label class="form-label">Max Concurrent Requests</label>
            <input
              v-model.number="settings.concurrency.max_concurrent_requests"
              type="number"
              class="form-input"
            />
          </div>
          <div class="form-checkbox-group">
            <input
              id="use_global_sem"
              v-model="settings.concurrency.use_global_semaphore"
              type="checkbox"
            />
            <label for="use_global_sem" class="form-label" style="margin-bottom: 0;">Dùng Semaphore toàn cục</label>
          </div>
        </div>

        <!-- Tab 5: Retry -->
        <div v-if="activeTab === 'retry'" class="form-container">
          <div class="form-group">
            <label class="form-label">Số lần thử lại tối đa</label>
            <input
              v-model.number="settings.retry.max_retries"
              type="number"
              class="form-input"
            />
          </div>
          <div class="form-group">
            <label class="form-label">Thời gian chờ ban đầu (s)</label>
            <input
              v-model.number="settings.retry.initial_delay"
              type="number"
              step="0.5"
              class="form-input"
            />
          </div>
          <div class="form-group">
            <label class="form-label">Thời gian chờ tối đa (s)</label>
            <input
              v-model.number="settings.retry.max_delay"
              type="number"
              step="1"
              class="form-input"
            />
          </div>
          <div class="form-group">
            <label class="form-label">Hệ số mũ (Exponential Base)</label>
            <input
              v-model.number="settings.retry.exponential_base"
              type="number"
              step="0.5"
              class="form-input"
            />
          </div>
          <div class="form-checkbox-group">
            <input
              id="jitter"
              v-model="settings.retry.jitter"
              type="checkbox"
            />
            <label for="jitter" class="form-label" style="margin-bottom: 0;">Jitter ngẫu nhiên</label>
          </div>
        </div>

        <!-- Save Button -->
        <div style="margin-top: 32px; padding-top: 20px; border-top: 1px solid var(--hairline);">
          <button class="btn btn-filled" @click="saveSettings">
            Lưu Thiết Lập
          </button>
        </div>
      </div>
    </div>
    <div v-else class="loading-state">
      Đang tải thiết lập...
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'

const settings = ref(null)
const activeTab = ref('model')

const tabs = [
  { id: 'model', name: 'Mô hình' },
  { id: 'translation', name: 'Dịch thuật' },
  { id: 'features', name: 'Tính năng' },
  { id: 'concurrency', name: 'Đồng thời' },
  { id: 'retry', name: 'Thử lại' },
]

async function loadSettings() {
  try {
    const res = await fetch('/api/settings')
    if (res.ok) {
      settings.value = await res.json()
    }
  } catch (err) {
    console.error('Failed to load settings:', err)
  }
}

async function saveSettings() {
  try {
    const res = await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(settings.value),
    })
    if (res.ok) {
      alert('Đã lưu thiết lập thành công!')
    } else {
      alert('Không thể lưu thiết lập!')
    }
  } catch (err) {
    console.error('Failed to save settings:', err)
    alert('Lỗi kết nối khi lưu thiết lập!')
  }
}

onMounted(() => {
  loadSettings()
})
</script>

<style scoped>
.settings-page {
  max-width: 800px;
  margin: 0 auto;
}

.page-header {
  margin-bottom: 24px;
}

.form-container {
  display: flex;
  flex-direction: column;
  gap: 20px;
  max-width: 500px;
}

.grid-checkboxes {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
  max-width: 100%;
}

.loading-state {
  text-align: center;
  padding: 48px;
  color: var(--stone);
}
</style>
