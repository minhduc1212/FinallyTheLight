const { createApp, ref, computed, onMounted, nextTick } = Vue;

createApp({
  setup() {
    // ── State Variables ──────────────────────────────────────────────────────
    const viewMode = ref('landing'); // 'landing' or 'app'
    const currentProject = ref('default_project');
    const projects = ref([]);
    const genres = ref({});
    const selectedGenre = ref('default');
    const showAllGenres = ref(false);
    
    // Translation options
    const sourceLang = ref('auto');
    const targetLang = ref('vi');
    const sourceText = ref('');
    const translatedText = ref('');
    const uploadedFile = ref(null);
    const fileInput = ref(null);
    
    // UI controls
    const drawers = ref({
      glossary: false,
      history: false,
      settings: false
    });
    const glossaryTab = ref('terms'); // 'terms' or 'characters'
    const glossarySearch = ref('');
    const showLogsPanel = ref(false);
    
    // Custom language dropdown states
    const showSourceLangDropdown = ref(false);
    const showTargetLangDropdown = ref(false);
    const showProjectDropdown = ref(false);

    const languageLabels = {
      auto: 'Tự động phát hiện (Auto)',
      zh: 'Tiếng Trung (ZH)',
      en: 'Tiếng Anh (EN)',
      ja: 'Tiếng Nhật (JA)',
      ko: 'Tiếng Hàn (KO)',
      vi: 'Tiếng Việt (VI)',
      id: 'Tiếng Indonesia (ID)'
    };

    function getLanguageLabel(code) {
      return languageLabels[code] || code;
    }

    function getLogClass(log) {
      if (log.includes('✅') || log.includes('completed') || log.includes('Done')) {
        return 'log-line-success';
      }
      if (log.includes('❌') || log.includes('failed') || log.includes('error') || log.includes('Error')) {
        return 'log-line-error';
      }
      if (log.includes('⚠️') || log.includes('WARNING') || log.includes('Conflict') || log.includes('retry') || log.includes('Retrying')) {
        return 'log-line-warning';
      }
      return '';
    }


    function toggleLangDropdown(type) {
      if (type === 'source') {
        showSourceLangDropdown.value = !showSourceLangDropdown.value;
        showTargetLangDropdown.value = false;
      } else {
        showTargetLangDropdown.value = !showTargetLangDropdown.value;
        showSourceLangDropdown.value = false;
      }
      nextTick(() => {
        lucide.createIcons();
      });
    }

    function selectSourceLang(code) {
      sourceLang.value = code;
      showSourceLangDropdown.value = false;
    }

    function selectTargetLang(code) {
      targetLang.value = code;
      showTargetLangDropdown.value = false;
    }

    
    // Glossary details
    const glossary = ref({
      terms: {},
      characters: {}
    });
    const newGlossaryKey = ref('');
    const newGlossaryVal = ref('');
    
    // Settings configuration
    const settings = ref({
      concurrency: { max_concurrent_requests: 2, use_global_semaphore: true },
      features: {
        auto_glossary: true,
        auto_summary: true,
        clean_thinking_tags: true,
        detect_duplicate_translation: true,
        editing_and_proofreading: true,
        inject_glossary_in_system_prompt: true,
        relevance_filtering: true,
        rolling_history: true,
        use_async_client: true
      },
      model: { name: 'gemma-4-31b-it', temperature: 0.25, top_p: 0.9 },
      retry: { max_retries: 5, initial_delay: 2.0, exponential_base: 2.0, max_delay: 60.0, jitter: true },
      translation: { chunk_size: 4000, max_workers: 2, target_language: 'vi', genre: 'default' }
    });
    const apiKey = ref('');
    
    // Modals
    const showNewProjectModal = ref(false);
    const newProjectName = ref('');
    const showAuthModal = ref(false);
    
    // Task Status
    const projectStatus = ref({
      status: 'idle',
      current_chunk: 0,
      total_chunks: 0,
      step: 'Idle',
      logs: [],
      error: null,
      output_file: null
    });
    
    let pollInterval = null;
    const logBody = ref(null);

    // ── Computed Properties ──────────────────────────────────────────────────
    const charCount = computed(() => sourceText.value ? sourceText.value.length : 0);
    const translatedCharCount = computed(() => translatedText.value ? translatedText.value.length : 0);
    
    const progressPct = computed(() => {
      if (!projectStatus.value.total_chunks) return 0;
      return Math.round((projectStatus.value.current_chunk / projectStatus.value.total_chunks) * 100);
    });

    const hasCheckpoint = computed(() => {
      return projectStatus.value.step && projectStatus.value.step.includes('Checkpoint available');
    });

    // Filtering glossary terms/characters
    const filteredTerms = computed(() => {
      const search = glossarySearch.value.toLowerCase().trim();
      if (!search) return glossary.value.terms;
      const res = {};
      for (const [k, v] of Object.entries(glossary.value.terms)) {
        if (k.toLowerCase().includes(search) || v.toLowerCase().includes(search)) {
          res[k] = v;
        }
      }
      return res;
    });

    const filteredCharacters = computed(() => {
      const search = glossarySearch.value.toLowerCase().trim();
      if (!search) return glossary.value.characters;
      const res = {};
      for (const [k, v] of Object.entries(glossary.value.characters)) {
        if (k.toLowerCase().includes(search) || v.toLowerCase().includes(search)) {
          res[k] = v;
        }
      }
      return res;
    });

    // Rendered HTML with tooltips for glossary matches
    const renderedTranslationHTML = computed(() => {
      if (!translatedText.value) return '';
      
      // Escape HTML
      let html = translatedText.value
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");

      const terms = Object.keys(glossary.value.terms || {}).sort((a, b) => b.length - a.length);
      const chars = Object.keys(glossary.value.characters || {}).sort((a, b) => b.length - a.length);

      const placeholders = [];
      let placeholderIndex = 0;

      for (const term of terms) {
        if (!term.trim()) continue;
        const translation = glossary.value.terms[term];
        const escapedTerm = term.replace(/[-\/\\^$*+?.()|[\]{}]/g, '\\$&');
        // Direct matching for global and case-insensitive replacements without \b word boundary issues
        const regex = new RegExp(escapedTerm, 'gi');
        
        html = html.replace(regex, (match) => {
          const ph = `\uE000${placeholderIndex}\uE001`;
          placeholders.push({
            placeholder: ph,
            html: `<span class="glossary-chip" data-tooltip="${term} → ${translation}">${match}</span>`
          });
          placeholderIndex++;
          return ph;
        });
      }

      for (const name of chars) {
        if (!name.trim()) continue;
        const info = glossary.value.characters[name];
        const parts = info.split('|').map(p => p.trim());
        const dispInfo = `${name} → ${parts[0] || ''} (${parts[1] || 'Nhân vật'}) [${parts[2] || 'xưng hô'}]`;
        const escapedName = name.replace(/[-\/\\^$*+?.()|[\]{}]/g, '\\$&');
        const regex = new RegExp(escapedName, 'gi');

        html = html.replace(regex, (match) => {
          const ph = `\uE002${placeholderIndex}\uE003`;
          placeholders.push({
            placeholder: ph,
            html: `<span class="glossary-chip character-chip" data-tooltip="${dispInfo}">${match}</span>`
          });
          placeholderIndex++;
          return ph;
        });
      }

      // Re-inject placeholders
      for (const item of placeholders) {
        html = html.replace(item.placeholder, item.html);
      }

      // Preserve paragraph newlines
      return html.replace(/\n/g, '<br>');
    });

    // ── Life Cycle ────────────────────────────────────────────────────────────
    onMounted(() => {
      // Re-trigger Lucide icons rendering
      setTimeout(() => {
        lucide.createIcons();
      }, 500);

      loadGenres();
      loadSettings();
      loadProjects();

      // Click outside to close language and project dropdowns
      window.addEventListener('click', (e) => {
        if (!e.target.closest('.custom-dropdown') && !e.target.closest('.project-select-wrapper')) {
          showSourceLangDropdown.value = false;
          showTargetLangDropdown.value = false;
          showProjectDropdown.value = false;
        }
      });
    });

    // ── API Operations ────────────────────────────────────────────────────────
    async function loadGenres() {
      try {
        const res = await fetch('/api/genres');
        if (res.ok) {
          const data = await res.json();
          genres.value = data.genres || {};
        }
      } catch (err) {
        console.error('Error loading genres:', err);
      }
    }

    async function loadSettings() {
      try {
        const res = await fetch('/api/settings');
        if (res.ok) {
          settings.value = await res.json();
          // Sync UI selected genre
          if (settings.value.translation && settings.value.translation.genre) {
            selectedGenre.value = settings.value.translation.genre;
          }
        }
      } catch (err) {
        console.error('Error loading settings:', err);
      }
    }

    async function saveSettings() {
      try {
        // Sync selected genre back to settings
        settings.value.translation.genre = selectedGenre.value;

        // Perform save settings request
        const res = await fetch('/api/settings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(settings.value)
        });

        if (res.ok) {
          // If custom api key is set in UI, save it to session / environment (mock/local only)
          if (apiKey.value) {
            // Note: Since this is local, we don't save API key in settings.yaml for security.
            // We can just keep it in memory or send it if we had a headers-based API.
            // In our simple backend, it uses .env, which is fine.
          }
          alert('Thiết lập cấu hình đã được lưu thành công.');
          drawers.value.settings = false;
        } else {
          const data = await res.json();
          alert('Lỗi lưu cấu hình: ' + data.detail);
        }
      } catch (err) {
        alert('Lỗi kết nối máy chủ: ' + err.message);
      }
    }

    async function loadProjects() {
      try {
        const res = await fetch('/api/projects');
        if (res.ok) {
          projects.value = await res.json();
          if (projects.value.length > 0 && !projects.value.includes(currentProject.value)) {
            currentProject.value = projects.value[0];
          }
          loadGlossary();
          checkStatus();
        }
      } catch (err) {
        console.error('Error loading projects:', err);
      }
    }

    async function createNewProject() {
      if (!newProjectName.value) return;
      const formattedName = newProjectName.value.trim().toLowerCase().replace(/\s+/g, '_');
      if (!projects.value.includes(formattedName)) {
        projects.value.push(formattedName);
      }
      currentProject.value = formattedName;
      newProjectName.value = '';
      showNewProjectModal.value = false;
      
      // Reset workspace
      sourceText.value = '';
      translatedText.value = '';
      uploadedFile.value = null;
      
      loadGlossary();
      checkStatus();
      alert(`Dự án "${formattedName}" đã được thiết lập thành công.`);
    }

    async function loadGlossary() {
      if (!currentProject.value) return;
      try {
        const res = await fetch(`/api/projects/${currentProject.value}/glossary`);
        if (res.ok) {
          glossary.value = await res.json();
        }
      } catch (err) {
        console.error('Error loading glossary:', err);
      }
    }

    async function addGlossaryItem() {
      if (!newGlossaryKey.value || !newGlossaryVal.value) return;
      
      const tab = glossaryTab.value;
      const endpoint = `/api/projects/${currentProject.value}/glossary/${tab === 'terms' ? 'term' : 'character'}`;
      const payload = tab === 'terms' 
        ? { term: newGlossaryKey.value.trim(), translation: newGlossaryVal.value.trim() }
        : { name: newGlossaryKey.value.trim(), info: newGlossaryVal.value.trim() };

      try {
        const res = await fetch(endpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });

        if (res.ok) {
          newGlossaryKey.value = '';
          newGlossaryVal.value = '';
          loadGlossary();
        } else {
          alert('Lỗi thêm thuật ngữ.');
        }
      } catch (err) {
        console.error(err);
      }
    }

    async function deleteGlossaryItem(type, name) {
      if (!confirm(`Xóa thuật ngữ/nhân vật "${name}"?`)) return;
      const endpoint = `/api/projects/${currentProject.value}/glossary/${type}/${encodeURIComponent(name)}`;
      try {
        const res = await fetch(endpoint, { method: 'DELETE' });
        if (res.ok) {
          loadGlossary();
        } else {
          alert('Không thể xóa thuật ngữ.');
        }
      } catch (err) {
        console.error(err);
      }
    }

    // ── Translation Trigger & Status Polling ──────────────────────────────
    async function triggerTranslate(resume = false) {
      if (!currentProject.value) {
        alert('Vui lòng chọn hoặc tạo dự án trước.');
        return;
      }

      const formData = new FormData();
      formData.append('genre', selectedGenre.value);
      formData.append('source_lang', sourceLang.value);
      formData.append('target_lang', targetLang.value);
      formData.append('resume', resume);

      if (!resume) {
        if (uploadedFile.value) {
          formData.append('file', uploadedFile.value);
        } else if (sourceText.value) {
          formData.append('text', sourceText.value);
        } else {
          alert('Vui lòng nhập văn bản hoặc tải lên tệp tin.');
          return;
        }
      }

      try {
        projectStatus.value.status = 'translating';
        projectStatus.value.step = 'Đang gửi yêu cầu...';
        projectStatus.value.error = null;
        translatedText.value = '';

        const res = await fetch(`/api/projects/${currentProject.value}/translate`, {
          method: 'POST',
          body: formData
        });

        if (!res.ok) {
          const data = await res.json();
          throw new Error(data.detail || 'Lỗi gửi yêu cầu dịch thuật');
        }

        // Expanded log panel automatically to let user see terminal progress
        showLogsPanel.value = true;
        
        // Start polling status
        startPolling();
      } catch (err) {
        projectStatus.value.status = 'failed';
        projectStatus.value.step = 'Lỗi khởi động';
        projectStatus.value.error = err.message;
        alert(err.message);
      }
    }

    async function checkStatus() {
      if (!currentProject.value) return;
      try {
        const res = await fetch(`/api/projects/${currentProject.value}/status`);
        if (res.ok) {
          const data = await res.json();
          projectStatus.value = data;
          
          // Scroll logs to bottom when updated
          nextTick(() => {
            if (logBody.value) {
              logBody.value.scrollTop = logBody.value.scrollHeight;
            }
          });

          // Handle completed state
          if (data.status === 'completed') {
            stopPolling();
            loadGlossary(); // Refresh glossary terms
            if (data.output_file) {
              fetchTranslationResult(data.output_file);
            }
          } else if (data.status === 'failed') {
            stopPolling();
            alert('Dịch thuật thất bại: ' + data.error);
          } else if (data.status === 'translating') {
            if (!pollInterval) {
              startPolling();
            }
          }
        }
      } catch (err) {
        console.error('Error fetching project status:', err);
      }
    }

    async function fetchTranslationResult(filename) {
      try {
        const res = await fetch(`/api/projects/${currentProject.value}/download/${filename}`);
        if (res.ok) {
          translatedText.value = await res.text();
        }
      } catch (err) {
        console.error('Error loading result content:', err);
      }
    }

    function startPolling() {
      stopPolling();
      pollInterval = setInterval(checkStatus, 1500);
    }

    function stopPolling() {
      if (pollInterval) {
        clearInterval(pollInterval);
        pollInterval = null;
      }
    }

    // Download/Export Actions
    function downloadTranslation() {
      if (!projectStatus.value.output_file) return;
      window.open(`/api/projects/${currentProject.value}/download/${projectStatus.value.output_file}`);
    }

    function downloadGlossaryReport() {
      window.open(`/api/projects/${currentProject.value}/download/${currentProject.value}_glossary_report.md`);
    }

    // ── Helper Actions ────────────────────────────────────────────────────────
    function toggleDrawer(name) {
      // Close all drawers first
      for (const d of Object.keys(drawers.value)) {
        if (d !== name) drawers.value[d] = false;
      }
      drawers.value[name] = !drawers.value[name];
      
      // Re-trigger Lucide icons rendering for drawer icons
      nextTick(() => {
        lucide.createIcons();
      });
    }

    function selectProject(proj) {
      currentProject.value = proj;
      loadGlossary();
      checkStatus();
      drawers.value.history = false;
      showProjectDropdown.value = false;
    }

    function onProjectChange() {
      loadGlossary();
      checkStatus();
    }

    function goToLanding() {
      viewMode.value = 'landing';
      nextTick(() => {
        lucide.createIcons();
      });
    }

    function clearInput() {
      sourceText.value = '';
      uploadedFile.value = null;
      translatedText.value = '';
      if (fileInput.value) {
        fileInput.value.value = '';
      }
    }

    function triggerFileSelect() {
      if (fileInput.value) {
        fileInput.value.click();
      }
    }

    function onFileChange(e) {
      if (e.target.files.length > 0) {
        uploadedFile.value = e.target.files[0];
        sourceText.value = ''; // Clear raw text if file uploaded
      }
    }

    function swapLanguages() {
      const src = sourceLang.value;
      const target = targetLang.value;
      
      sourceLang.value = target === 'auto' ? 'vi' : target;
      targetLang.value = src === 'auto' ? 'zh' : src;

      // Swap the text contents too!
      const tempText = sourceText.value;
      sourceText.value = translatedText.value;
      translatedText.value = tempText;

      // Close dropdowns
      showSourceLangDropdown.value = false;
      showTargetLangDropdown.value = false;
    }

    function onTextareaInput() {
      uploadedFile.value = null; // Clear file if user types
    }

    function formatBytes(bytes, decimals = 2) {
      if (bytes === 0) return '0 Bytes';
      const k = 1024;
      const dm = decimals < 0 ? 0 : decimals;
      const sizes = ['Bytes', 'KB', 'MB', 'GB'];
      const i = Math.floor(Math.log(bytes) / Math.log(k));
      return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
    }

    return {
      viewMode,
      currentProject,
      projects,
      genres,
      selectedGenre,
      showAllGenres,
      sourceLang,
      targetLang,
      sourceText,
      translatedText,
      uploadedFile,
      fileInput,
      drawers,
      glossaryTab,
      glossarySearch,
      showLogsPanel,
      showSourceLangDropdown,
      showTargetLangDropdown,
      showProjectDropdown,
      toggleLangDropdown,
      selectSourceLang,
      selectTargetLang,
      getLanguageLabel,
      getLogClass,
      glossary,
      newGlossaryKey,
      newGlossaryVal,
      settings,
      apiKey,
      showNewProjectModal,
      newProjectName,
      showAuthModal,
      projectStatus,
      charCount,
      translatedCharCount,
      progressPct,
      hasCheckpoint,
      filteredTerms,
      filteredCharacters,
      renderedTranslationHTML,
      logBody,
      saveSettings,
      createNewProject,
      addGlossaryItem,
      deleteGlossaryItem,
      triggerTranslate,
      downloadTranslation,
      downloadGlossaryReport,
      toggleDrawer,
      selectProject,
      onProjectChange,
      goToLanding,
      clearInput,
      triggerFileSelect,
      onFileChange,
      swapLanguages,
      onTextareaInput,
      formatBytes
    };
  }
}).mount('#app');
