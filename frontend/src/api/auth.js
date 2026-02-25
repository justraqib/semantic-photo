import axios from 'axios';
import { API_BASE_URL } from './baseUrl';

const api = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
});

api.interceptors.response.use(
  response => response,
  async error => {
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
  const frontendOrigin = encodeURIComponent(window.location.origin);
  window.location.href = `${API_BASE_URL}/auth/google?frontend_origin=${frontendOrigin}`;
};
export const loginWithGithub = () => {
  const frontendOrigin = encodeURIComponent(window.location.origin);
  window.location.href = `${API_BASE_URL}/auth/github?frontend_origin=${frontendOrigin}`;
};
