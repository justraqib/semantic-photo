import axios from 'axios';

import { getApiBaseUrl } from './baseUrl';

const API_BASE_URL = getApiBaseUrl();

const api = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
  timeout: 15000,
});

api.interceptors.response.use(
  response => response,
  async error => {
    const requestUrl = error.config?.url || '';
    if (error.response?.status === 401 && !error.config?._retry && !requestUrl.includes('/auth/refresh')) {
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
