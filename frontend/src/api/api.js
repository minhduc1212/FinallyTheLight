/**
 * Finally The Light — API Service Layer
 * Centralized API client for interacting with the backend.
 */

// Helper to construct query strings
function buildQueryString(params) {
  const parts = [];
  for (const key in params) {
    if (params[key] !== undefined && params[key] !== null) {
      parts.push(`${encodeURIComponent(key)}=${encodeURIComponent(params[key])}`);
    }
  }
  return parts.length ? `?${parts.join('&')}` : '';
}

// Unified request wrapper
async function request(url, options = {}) {
  const { json, ...customOptions } = options;
  const headers = { ...customOptions.headers };

  if (json) {
    headers['Content-Type'] = 'application/json';
    customOptions.body = JSON.stringify(json);
  }

  const response = await fetch(url, {
    ...customOptions,
    headers,
  });

  if (!response.ok) {
    let errorMessage = `API error: ${response.status} ${response.statusText}`;
    try {
      const errorData = await response.json();
      if (errorData && errorData.detail) {
        errorMessage = errorData.detail;
      }
    } catch (_) {
      // Ignore if response is not JSON
    }
    throw new Error(errorMessage);
  }

  // HEAD requests or empty content responses
  if (customOptions.method === 'HEAD' || response.status === 204) {
    return true;
  }

  // Return json data
  try {
    return await response.json();
  } catch (e) {
    // If not JSON, return plain text
    return response;
  }
}

export const api = {
  // ── Projects ──────────────────────────────────────────────
  
  /**
   * Fetch all project names
   */
  async getProjects() {
    return request('/api/projects');
  },

  /**
   * Create a new project
   * @param {string} name
   */
  async createProject(name) {
    return request(`/api/projects/${encodeURIComponent(name)}`, {
      method: 'POST'
    });
  },

  /**
   * Delete an existing project
   * @param {string} name
   */
  async deleteProject(name) {
    return request(`/api/projects/${encodeURIComponent(name)}`, {
      method: 'DELETE'
    });
  },

  /**
   * Get translation status of a project
   * @param {string} project
   */
  async getProjectStatus(project) {
    return request(`/api/projects/${encodeURIComponent(project)}/status`);
  },

  // ── Novels ────────────────────────────────────────────────

  /**
   * List all novels (filenames) in a project
   * @param {string} project
   */
  async getNovels(project) {
    return request(`/api/projects/${encodeURIComponent(project)}/novels`);
  },

  /**
   * Upload a novel text file
   * @param {string} project
   * @param {File} file
   */
  async uploadNovel(project, file) {
    const formData = new FormData();
    formData.append('file', file);
    return request(`/api/projects/${encodeURIComponent(project)}/novels`, {
      method: 'POST',
      body: formData
    });
  },

  /**
   * Delete a novel from a project
   * @param {string} project
   * @param {string} novel
   */
  async deleteNovel(project, novel) {
    return request(`/api/projects/${encodeURIComponent(project)}/novels/${encodeURIComponent(novel)}`, {
      method: 'DELETE'
    });
  },

  // ── Glossary & Characters ─────────────────────────────────

  /**
   * Fetch glossary and characters for a project
   * @param {string} project
   */
  async getGlossary(project) {
    return request(`/api/projects/${encodeURIComponent(project)}/glossary`);
  },

  /**
   * Add a term translation to the project glossary
   * @param {string} project
   * @param {string} term
   * @param {string} translation
   */
  async addTerm(project, term, translation) {
    return request(`/api/projects/${encodeURIComponent(project)}/glossary/term`, {
      method: 'POST',
      json: { term, translation }
    });
  },

  /**
   * Delete a term from the glossary
   * @param {string} project
   * @param {string} term
   */
  async deleteTerm(project, term) {
    return request(`/api/projects/${encodeURIComponent(project)}/glossary/term/${encodeURIComponent(term)}`, {
      method: 'DELETE'
    });
  },

  /**
   * Add a character to the project character directory
   * @param {string} project
   * @param {string} name
   * @param {string} info
   */
  async addCharacter(project, name, info) {
    return request(`/api/projects/${encodeURIComponent(project)}/glossary/character`, {
      method: 'POST',
      json: { name, info }
    });
  },

  /**
   * Delete a character entry
   * @param {string} project
   * @param {string} name
   */
  async deleteCharacter(project, name) {
    return request(`/api/projects/${encodeURIComponent(project)}/glossary/character/${encodeURIComponent(name)}`, {
      method: 'DELETE'
    });
  },

  // ── Chunks & Translation Tasks ───────────────────────────

  /**
   * Fetch novel chunks with pagination
   * @param {string} project
   * @param {string} novel
   * @param {number} page
   * @param {number} limit
   */
  async getNovelChunks(project, novel, page = 1, limit = 50) {
    const query = buildQueryString({ page, limit });
    return request(`/api/projects/${encodeURIComponent(project)}/novels/${encodeURIComponent(novel)}/chunks${query}`);
  },

  /**
   * Fetch checkpoints for the project's novels
   * @param {string} project
   */
  async getCheckpoints(project) {
    return request(`/api/projects/${encodeURIComponent(project)}/checkpoints`);
  },

  /**
   * Check if a translation output file exists and is ready for download
   * @param {string} project
   * @param {string} filename
   */
  async checkDownloadAvailable(project, filename) {
    try {
      await request(`/api/projects/${encodeURIComponent(project)}/download/${encodeURIComponent(filename)}`, {
        method: 'HEAD'
      });
      return true;
    } catch (_) {
      return false;
    }
  },

  /**
   * Get direct download URL for the translated file
   * @param {string} project
   * @param {string} filename
   */
  getDownloadUrl(project, filename) {
    return `/api/projects/${encodeURIComponent(project)}/download/${encodeURIComponent(filename)}`;
  },

  /**
   * Trigger a translation run (for selected chunks or whole file)
   * @param {string} project
   * @param {string} novel
   * @param {object} params
   * @param {Array<number>|null} params.target_chunks - Specific chunk IDs, or null to translate all
   * @param {string} params.genre
   * @param {string} params.source_lang
   * @param {string} params.target_lang
   * @param {boolean} params.resume
   */
  async translateChunks(project, novel, params) {
    return request(`/api/projects/${encodeURIComponent(project)}/novels/${encodeURIComponent(novel)}/translate_chunks`, {
      method: 'POST',
      json: {
        target_chunks: params.target_chunks,
        genre: params.genre,
        source_lang: params.source_lang,
        target_lang: params.target_lang,
        resume: params.resume
      }
    });
  },

  /**
   * Cancel / Pause current translation task
   * @param {string} project
   */
  async cancelTranslation(project) {
    return request(`/api/projects/${encodeURIComponent(project)}/cancel`, {
      method: 'POST'
    });
  },

  // ── Global Config & Settings ──────────────────────────────

  /**
   * Get all configuration genres and source/target languages
   */
  async getGenresConfig() {
    return request('/api/genres');
  },

  /**
   * Fetch global settings
   */
  async getSettings() {
    return request('/api/settings');
  },

  /**
   * Update global settings
   * @param {object} settings
   */
  async saveSettings(settings) {
    return request('/api/settings', {
      method: 'POST',
      json: settings
    });
  }
};
