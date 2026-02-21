import axios from 'axios';

const api = axios.create({
  baseURL: 'http://localhost:8000',
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
  window.location.href = 'http://localhost:8000/auth/google/login';
};