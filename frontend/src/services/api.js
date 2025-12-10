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

  generateOutline: async (keywordId, contentType, existingUrl = null, targetIntent = null) => {
    const response = await api.post('/api/outline/generate', {
      keyword_id: keywordId,
      content_type: contentType,
      existing_url: existingUrl,
      target_intent: targetIntent
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

// Auth API
export const authAPI = {
  login: async (username, password) => {
    const response = await api.post('/api/auth/login', { username, password });
    return response.data;
  },

  getMe: async () => {
    const response = await api.get('/api/auth/me');
    return response.data;
  }
};

export default api;

