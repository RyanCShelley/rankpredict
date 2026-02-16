import axios from 'axios';
import Cookies from 'js-cookie';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

console.log('🔗 API Base URL:', API_BASE_URL);

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 300000, // 5 minutes for scoring operations
});

// Add request interceptor
api.interceptors.request.use(
  (config) => {
    const token = Cookies.get('auth_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    console.log('📤 API Request:', config.method?.toUpperCase(), config.url);
    return config;
  },
  (error) => Promise.reject(error)
);

// Add response interceptor
api.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('❌ API Error:', error.response?.status, error.response?.data);
    if (error.response?.status === 401) {
      Cookies.remove('auth_token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// Strategy Dashboard API
export const strategyAPI = {
  createList: async (name, targetDomainUrl, keywords, clientProfile = null) => {
    const payload = {
      name,
      target_domain_url: targetDomainUrl,
      keywords
    };
    if (clientProfile) {
      payload.client_profile = clientProfile;
    }
    const response = await api.post('/api/strategy/lists', payload);
    return response.data;
  },

  getLists: async () => {
    const response = await api.get('/api/strategy/lists');
    return response.data;
  },

  getList: async (listId) => {
    const response = await api.get(`/api/strategy/lists/${listId}`);
    return response.data;
  },

  scoreKeywords: async (listId, forceRescore = false) => {
    const response = await api.post(`/api/strategy/lists/${listId}/score?force_rescore=${forceRescore}`);
    return response.data;
  },

  updateKeyword: async (keywordId, updates) => {
    const response = await api.patch(`/api/strategy/keywords/${keywordId}`, updates);
    return response.data;
  },

  deleteList: async (listId) => {
    const response = await api.delete(`/api/strategy/lists/${listId}`);
    return response.data;
  },

  deleteKeyword: async (keywordId) => {
    const response = await api.delete(`/api/strategy/keywords/${keywordId}`);
    return response.data;
  },

  addKeywords: async (listId, keywords) => {
    const response = await api.post(`/api/strategy/lists/${listId}/keywords`, {
      keywords
    });
    return response.data;
  },

  scoreSelectedKeywords: async (listId, keywordIds, onProgress) => {
    const MAX_RETRIES = 3;
    let remainingIds = [...keywordIds];
    let lastError = null;

    for (let attempt = 0; attempt < MAX_RETRIES; attempt++) {
      if (remainingIds.length === 0) break;

      if (attempt > 0) {
        // Exponential backoff: 2s, 4s
        await new Promise(r => setTimeout(r, 1000 * Math.pow(2, attempt)));
        console.log(`🔄 Retry attempt ${attempt + 1}/${MAX_RETRIES} for ${remainingIds.length} keywords`);
      }

      try {
        const token = Cookies.get('auth_token');
        const response = await fetch(`${API_BASE_URL}/api/strategy/lists/${listId}/score-selected`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({ keyword_ids: remainingIds }),
        });

        if (!response.ok) {
          const err = await response.json().catch(() => ({ detail: response.statusText }));
          throw new Error(err.detail || 'Scoring failed');
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let completed = false;
        const scoredIds = new Set();

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });

          const lines = buffer.split('\n');
          buffer = lines.pop(); // keep incomplete line in buffer

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const event = JSON.parse(line.slice(6));
                if (event.type === 'scored' && event.keyword_id) {
                  // Track keywords confirmed scored (after DB commit)
                  scoredIds.add(event.keyword_id);
                }
                if (event.type === 'done') {
                  completed = true;
                }
                if (onProgress) onProgress(event);
              } catch { /* ignore parse errors */ }
            }
          }
        }

        if (completed) {
          remainingIds = [];
          break; // All done
        }

        // Stream ended without 'done' event — connection dropped mid-scoring
        // Remove already-scored keywords from the retry list
        remainingIds = remainingIds.filter(id => !scoredIds.has(id));
        if (remainingIds.length === 0) break;
        lastError = new Error('Connection lost during scoring');

      } catch (err) {
        lastError = err;
        // On network error, remainingIds stays as-is for retry
        console.error(`Scoring attempt ${attempt + 1} failed:`, err.message);
      }
    }

    if (remainingIds.length > 0 && lastError) {
      throw lastError;
    }
  },

  updateList: async (listId, updates) => {
    const response = await api.patch(`/api/strategy/lists/${listId}`, updates);
    return response.data;
  },

  fetchVolumes: async (listId) => {
    const response = await api.post(`/api/strategy/lists/${listId}/fetch-volumes`);
    return response.data;
  }
};

// Outline Builder API
export const outlineAPI = {
  getProjects: async () => {
    const response = await api.get('/api/outline/projects');
    return response.data;
  },

  getKeywordsByProject: async (listId) => {
    const response = await api.get(`/api/outline/keywords?list_id=${listId}`);
    return response.data;
  },

  getSelectedKeywords: async () => {
    const response = await api.get('/api/outline/keywords');
    return response.data;
  },

  generateOutline: async (keywordId, contentType, existingUrl = null, targetIntent = null, existingContent = null, forceRefresh = false) => {
    const response = await api.post('/api/outline/generate', {
      keyword_id: keywordId,
      content_type: contentType,
      existing_url: existingUrl,
      target_intent: targetIntent,
      existing_content: existingContent,
      force_refresh: forceRefresh
    });
    return response.data;
  },

  getImprovementPlan: async (keywordId, existingUrl) => {
    const response = await api.get(`/api/outline/improvement-plan/${keywordId}`, {
      params: { existing_url: existingUrl }
    });
    return response.data;
  },

  // Saved briefs
  getSavedBriefs: async (listId = null) => {
    const url = listId ? `/api/outline/briefs?list_id=${listId}` : '/api/outline/briefs';
    const response = await api.get(url);
    return response.data;
  },

  getSavedBrief: async (briefId) => {
    const response = await api.get(`/api/outline/briefs/${briefId}`);
    return response.data;
  },

  deleteBrief: async (briefId) => {
    const response = await api.delete(`/api/outline/briefs/${briefId}`);
    return response.data;
  },

  downloadBriefPdf: async (briefId) => {
    const response = await api.get(`/api/outline/briefs/${briefId}/pdf`, {
      responseType: 'blob'
    });
    return response.data;
  }
};

// Strategy Development API
export const strategyDevAPI = {
  // Projects
  getProjects: async () => {
    const response = await api.get('/api/strategy-dev/projects');
    return response.data;
  },

  createProject: async (name, domain = null, coreTopics = null) => {
    const response = await api.post('/api/strategy-dev/projects', {
      name,
      domain,
      core_topics: coreTopics
    });
    return response.data;
  },

  getProjectStats: async (projectId) => {
    const response = await api.get(`/api/strategy-dev/projects/${projectId}/stats`);
    return response.data;
  },

  getProject: async (projectId, topicFilter = null, stageFilter = null) => {
    let url = `/api/strategy-dev/projects/${projectId}`;
    const params = [];
    if (topicFilter) params.push(`topic_filter=${encodeURIComponent(topicFilter)}`);
    if (stageFilter) params.push(`stage_filter=${encodeURIComponent(stageFilter)}`);
    if (params.length) url += '?' + params.join('&');
    const response = await api.get(url);
    return response.data;
  },

  updateProject: async (projectId, updates) => {
    const response = await api.put(`/api/strategy-dev/projects/${projectId}`, updates);
    return response.data;
  },

  deleteProject: async (projectId) => {
    const response = await api.delete(`/api/strategy-dev/projects/${projectId}`);
    return response.data;
  },

  // GSC
  getGscAuthUrl: async (projectId) => {
    const response = await api.get(`/api/strategy-dev/gsc/auth-url?project_id=${projectId}`);
    return response.data;
  },

  listGscSites: async (projectId) => {
    const response = await api.get(`/api/strategy-dev/gsc/sites?project_id=${projectId}`);
    return response.data;
  },

  // Sync
  syncProject: async (projectId, maxPosition = null) => {
    let url = `/api/strategy-dev/projects/${projectId}/sync`;
    if (maxPosition !== null) {
      url += `?max_position=${maxPosition}`;
    }
    const response = await api.post(url);
    return response.data;
  },

  // Export
  exportKeywordsCsv: async (keywordIds) => {
    const params = keywordIds.map(id => `keyword_ids=${id}`).join('&');
    const response = await api.post(`/api/strategy-dev/keywords/export-csv?${params}`, null, {
      responseType: 'blob'
    });
    return response.data;
  },

  addKeywordsToList: async (keywordIds, listId = null, newListName = null, targetDomainUrl = null) => {
    const response = await api.post('/api/strategy-dev/keywords/add-to-list', {
      keyword_ids: keywordIds,
      list_id: listId,
      new_list_name: newListName,
      target_domain_url: targetDomainUrl
    });
    return response.data;
  },

  // Visualization
  getTopicGraphData: async (projectId, topic) => {
    const response = await api.get(`/api/strategy-dev/projects/${projectId}/topic-graph?topic=${encodeURIComponent(topic)}`);
    return response.data;
  },

  // Funnel View
  getFunnelData: async (projectId, topic = null) => {
    let url = `/api/strategy-dev/projects/${projectId}/funnel`;
    if (topic) url += `?topic=${encodeURIComponent(topic)}`;
    const response = await api.get(url);
    return response.data;
  },

  // Keyword Management
  updateKeywordStage: async (keywordId, stage) => {
    const response = await api.patch(`/api/strategy-dev/keywords/${keywordId}/stage`, { stage });
    return response.data;
  },

  deleteStrategyKeyword: async (keywordId) => {
    const response = await api.delete(`/api/strategy-dev/keywords/${keywordId}`);
    return response.data;
  },

  // Query Fanning
  generateQueries: async (projectId, stage, topic) => {
    const response = await api.post(`/api/strategy-dev/projects/${projectId}/generate-queries`, {
      stage,
      topic
    });
    return response.data;
  },

  // Funnel Export
  exportFunnelCsv: async (projectId, topic = null) => {
    let url = `/api/strategy-dev/projects/${projectId}/funnel/export-csv`;
    if (topic) url += `?topic=${encodeURIComponent(topic)}`;
    const response = await api.get(url, { responseType: 'blob' });
    return response.data;
  },

  exportFunnelPdf: async (projectId, topic = null) => {
    let url = `/api/strategy-dev/projects/${projectId}/funnel/export-pdf`;
    if (topic) url += `?topic=${encodeURIComponent(topic)}`;
    const response = await api.get(url, { responseType: 'blob' });
    return response.data;
  },

  // Fetch Volumes
  fetchStrategyVolumes: async (projectId, keywordIds = null) => {
    let url = `/api/strategy-dev/projects/${projectId}/fetch-volumes`;
    if (keywordIds && keywordIds.length > 0) {
      const params = keywordIds.map(id => `keyword_ids=${id}`).join('&');
      url += `?${params}`;
    }
    const response = await api.post(url);
    return response.data;
  },

  // Persona
  generatePersona: async (projectId, description) => {
    const response = await api.post(`/api/strategy-dev/projects/${projectId}/generate-persona`, { description });
    return response.data;
  },

  // Delete Multiple Keywords
  deleteKeywordsBulk: async (keywordIds) => {
    const params = keywordIds.map(id => `keyword_ids=${id}`).join('&');
    const response = await api.post(`/api/strategy-dev/keywords/delete-bulk?${params}`);
    return response.data;
  }
};

// Auth API
export const authAPI = {
  login: async (username, password) => {
    const response = await api.post('/api/auth/login', { username, password });
    return response.data;
  },

  getMe: async () => {
    const response = await api.get('/api/auth/me');
    return response.data;
  },

  // Admin user management
  getUsers: async () => {
    const response = await api.get('/api/auth/users');
    return response.data;
  },

  createUser: async (userData) => {
    const response = await api.post('/api/auth/users', userData);
    return response.data;
  },

  updateUser: async (userId, updates) => {
    const response = await api.put(`/api/auth/users/${userId}`, updates);
    return response.data;
  },

  deleteUser: async (userId) => {
    const response = await api.delete(`/api/auth/users/${userId}`);
    return response.data;
  }
};

export default api;

