import axios from 'axios';

import { getApiBaseUrl } from './baseUrl';

const API_BASE_URL = getApiBaseUrl();

const searchApi = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
  timeout: 15000,
});

searchApi.interceptors.response.use(
  (response) => response,
  async (error) => {
    const requestUrl = error.config?.url || '';
    if (error.response?.status === 401 && !error.config?._retry && !requestUrl.includes('/auth/refresh')) {
      error.config._retry = true;
      try {
        await searchApi.post('/auth/refresh');
        return searchApi(error.config);
      } catch {
        if (window.location.pathname !== '/login') {
          window.location.href = '/login';
        }
      }
    }
    return Promise.reject(error);
  }
);

export const searchPhotos = (query, params = {}) =>
  searchApi.get('/search', {
    params: { q: query, ...params },
  });
