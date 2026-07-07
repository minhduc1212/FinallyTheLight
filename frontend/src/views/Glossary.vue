<template>
  <div class="glossary-page">
    <div class="page-header">
      <h2>Thuật ngữ Dự án <span class="subtitle">— {{ project }}</span></h2>
    </div>

    <!-- Tab Selection -->
    <div class="card" style="padding: 0; overflow: hidden; margin-bottom: 24px;">
      <div class="tab-bar">
        <button
          class="tab-item"
          :class="{ active: activeTab === 'terms' }"
          @click="activeTab = 'terms'"
        >
          Từ điển Thuật ngữ
        </button>
        <button
          class="tab-item"
          :class="{ active: activeTab === 'characters' }"
          @click="activeTab = 'characters'"
        >
          Danh sách Nhân vật
        </button>
      </div>
    </div>

    <!-- TERMS TAB -->
    <div v-if="activeTab === 'terms'">
      <!-- Add Form -->
      <div class="card" style="margin-bottom: 24px;">
        <h3 style="font-size: 16px; font-weight: 600; margin-bottom: 16px;">Thêm Thuật Ngữ Mới</h3>
        <form @submit.prevent="addTerm" style="display: flex; gap: 16px; align-items: flex-end; flex-wrap: wrap;">
          <div class="form-group" style="flex: 1; min-width: 200px; margin-bottom: 0;">
            <label class="form-label">Từ gốc (Tiếng Trung/Anh...)</label>
            <input
              v-model="newTerm.term"
              type="text"
              class="form-input"
              placeholder="Ví dụ: torpor"
              required
            />
          </div>
          <div class="form-group" style="flex: 1; min-width: 200px; margin-bottom: 0;">
            <label class="form-label">Nghĩa (Tiếng Việt)</label>
            <input
              v-model="newTerm.translation"
              type="text"
              class="form-input"
              placeholder="Ví dụ: ngủ đông"
              required
            />
          </div>
          <button type="submit" class="btn btn-filled" :disabled="!newTerm.term.trim() || !newTerm.translation.trim()">
            Thêm
          </button>
        </form>
      </div>

      <!-- Terms Table -->
      <div class="data-table-wrapper">
        <table class="data-table" v-if="termsList.length > 0">
          <thead>
            <tr>
              <th>Từ gốc</th>
              <th>Nghĩa dịch</th>
              <th style="width: 100px;">Hành động</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="t in termsList" :key="t.term">
              <td style="font-weight: 500;">{{ t.term }}</td>
              <td>{{ t.translation }}</td>
              <td>
                <button class="btn btn-danger" @click="deleteTerm(t.term)">Xóa</button>
              </td>
            </tr>
          </tbody>
        </table>
        <div v-else class="empty-state">
          Chưa có thuật ngữ nào được tạo. Thuật ngữ sẽ tự động được trích xuất trong lúc dịch hoặc bạn có thể thêm thủ công.
        </div>
      </div>
    </div>

    <!-- CHARACTERS TAB -->
    <div v-if="activeTab === 'characters'">
      <!-- Add Form -->
      <div class="card" style="margin-bottom: 24px;">
        <h3 style="font-size: 16px; font-weight: 600; margin-bottom: 16px;">Thêm Nhân Vật Mới</h3>
        <form @submit.prevent="addCharacter" style="display: flex; gap: 16px; align-items: flex-end; flex-wrap: wrap;">
          <div class="form-group" style="flex: 1; min-width: 200px; margin-bottom: 0;">
            <label class="form-label">Tên gốc (Ví dụ: 林风 / Ariadne)</label>
            <input
              v-model="newChar.name"
              type="text"
              class="form-input"
              placeholder="Ví dụ: 林风"
              required
            />
          </div>
          <div class="form-group" style="flex: 2; min-width: 300px; margin-bottom: 0;">
            <label class="form-label">Thông tin (tên dịch | vai trò | xưng hô)</label>
            <input
              v-model="newChar.info"
              type="text"
              class="form-input"
              placeholder="Ví dụ: Lâm Phong | nam chính, đệ tử Thanh Vân Môn | ta / hắn"
              required
            />
          </div>
          <button type="submit" class="btn btn-filled" :disabled="!newChar.name.trim() || !newChar.info.trim()">
            Thêm
          </button>
        </form>
      </div>

      <!-- Characters Table -->
      <div class="data-table-wrapper">
        <table class="data-table" v-if="charactersList.length > 0">
          <thead>
            <tr>
              <th style="width: 200px;">Tên gốc</th>
              <th>Thông tin nhân vật (Dịch | Vai trò | Xưng hô)</th>
              <th style="width: 100px;">Hành động</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="c in charactersList" :key="c.name">
              <td style="font-weight: 500;">{{ c.name }}</td>
              <td>
                <div style="display: flex; gap: 8px; flex-wrap: wrap; align-items: center;">
                  <span class="char-badge" v-for="(part, i) in splitInfo(c.info)" :key="i">
                    {{ part }}
                  </span>
                </div>
              </td>
              <td>
                <button class="btn btn-danger" @click="deleteCharacter(c.name)">Xóa</button>
              </td>
            </tr>
          </tbody>
        </table>
        <div v-else class="empty-state">
          Chưa có nhân vật nào được tạo. Hệ thống sẽ tự động học hỏi nhân vật mới từ văn bản trong lúc dịch.
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '@/api/api'

const route = useRoute()
const project = computed(() => route.params.project)

const activeTab = ref('terms')
const termsList = ref([])
const charactersList = ref([])

const newTerm = ref({ term: '', translation: '' })
const newChar = ref({ name: '', info: '' })

async function loadGlossary() {
  if (!project.value) return
  try {
    const data = await api.getGlossary(project.value)
    
    // Convert dict of terms {"term": "translation"} to array of objects
    if (data.terms) {
      termsList.value = Object.entries(data.terms).map(([term, translation]) => ({
        term,
        translation
      }))
    } else {
      termsList.value = []
    }

    // Convert dict of characters {"name": "info"} to array of objects
    if (data.characters) {
      charactersList.value = Object.entries(data.characters).map(([name, info]) => ({
        name,
        info
      }))
    } else {
      charactersList.value = []
    }
  } catch (err) {
    console.error('Failed to load glossary:', err)
  }
}

async function addTerm() {
  const term = newTerm.value.term.trim()
  const translation = newTerm.value.translation.trim()
  if (!term || !translation) return

  try {
    await api.addTerm(project.value, term, translation)
    newTerm.value = { term: '', translation: '' }
    await loadGlossary()
  } catch (err) {
    console.error('Failed to add term:', err)
  }
}

async function deleteTerm(term) {
  if (!confirm(`Xóa thuật ngữ "${term}"?`)) return
  try {
    await api.deleteTerm(project.value, term)
    await loadGlossary()
  } catch (err) {
    console.error('Failed to delete term:', err)
  }
}

async function addCharacter() {
  const name = newChar.value.name.trim()
  const info = newChar.value.info.trim()
  if (!name || !info) return

  try {
    await api.addCharacter(project.value, name, info)
    newChar.value = { name: '', info: '' }
    await loadGlossary()
  } catch (err) {
    console.error('Failed to add character:', err)
  }
}

async function deleteCharacter(name) {
  if (!confirm(`Xóa nhân vật "${name}"?`)) return
  try {
    await api.deleteCharacter(project.value, name)
    await loadGlossary()
  } catch (err) {
    console.error('Failed to delete character:', err)
  }
}

function splitInfo(info) {
  if (!info) return []
  return info.split('|').map(s => s.trim()).filter(Boolean)
}

watch(project, () => {
  loadGlossary()
}, { immediate: true })

onMounted(() => {
  loadGlossary()
})
</script>

<style scoped>
.subtitle {
  font-size: 18px;
  color: var(--color-slate);
  font-weight: 400;
}

.empty-state {
  text-align: center;
  padding: 48px;
  color: var(--color-stone);
  font-size: 14px;
}

.char-badge {
  background: var(--color-mist);
  color: var(--color-slate);
  padding: 4px 10px;
  border-radius: var(--radius-pills);
  font-size: 13px;
  font-weight: 500;
  border: 1px solid var(--color-hairline);
}
</style>
