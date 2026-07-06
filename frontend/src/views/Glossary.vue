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
    const res = await fetch(`/api/projects/${project.value}/glossary`)
    if (res.ok) {
      const data = await res.json()
      
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
    const res = await fetch(`/api/projects/${project.value}/glossary/term`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ term, translation })
    })
    if (res.ok) {
      newTerm.value = { term: '', translation: '' }
      await loadGlossary()
    }
  } catch (err) {
    console.error('Failed to add term:', err)
  }
}

async function deleteTerm(term) {
  if (!confirm(`Xóa thuật ngữ "${term}"?`)) return
  try {
    const res = await fetch(`/api/projects/${project.value}/glossary/term/${encodeURIComponent(term)}`, {
      method: 'DELETE'
    })
    if (res.ok) {
      await loadGlossary()
    }
  } catch (err) {
    console.error('Failed to delete term:', err)
  }
}

async function addCharacter() {
  const name = newChar.value.name.trim()
  const info = newChar.value.info.trim()
  if (!name || !info) return

  try {
    const res = await fetch(`/api/projects/${project.value}/glossary/character`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, info })
    })
    if (res.ok) {
      newChar.value = { name: '', info: '' }
      await loadGlossary()
    }
  } catch (err) {
    console.error('Failed to add character:', err)
  }
}

async function deleteCharacter(name) {
  if (!confirm(`Xóa nhân vật "${name}"?`)) return
  try {
    const res = await fetch(`/api/projects/${project.value}/glossary/character/${encodeURIComponent(name)}`, {
      method: 'DELETE'
    })
    if (res.ok) {
      await loadGlossary()
    }
  } catch (err) {
    console.error('Failed to delete character:', err)
  }
}

function splitInfo(info) {
  if (!info) return []
  return info.split('|').map(p => p.trim()).filter(Boolean)
}

watch(project, () => {
  loadGlossary()
})

onMounted(() => {
  loadGlossary()
})
</script>

<style scoped>
.subtitle {
  font-size: 18px;
  color: var(--slate);
  font-weight: 400;
}

.char-badge {
  background: var(--mist);
  color: var(--ink);
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 4px;
  border: 1px solid var(--hairline);
}

.empty-state {
  text-align: center;
  padding: 48px 32px;
  color: var(--stone);
  font-size: 14px;
}
</style>
