import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const DEV_PREVIEW = !import.meta.env.VITE_API_URL && typeof window !== 'undefined' && !window.location.hostname.includes('localhost:8000');

const api = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
});

api.interceptors.response.use(
  response => response,
  async error => {
    // In dev preview mode, don't redirect on API failures
    if (DEV_PREVIEW) {
      return Promise.reject(error);
    }
    if (error.response?.status === 401 && !error.config._retry) {
      error.config._retry = true;
      try {
        await api.post('/auth/refresh');
        return api(error.config);
      } catch {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

export const getMe = () => api.get('/auth/me');
export const logout = () => api.post('/auth/logout');
export const loginWithGoogle = () => {
  window.location.href = `${API_BASE_URL}/auth/google`;
};
export const loginWithGithub = () => {
  window.location.href = `${API_BASE_URL}/auth/github`;
};
