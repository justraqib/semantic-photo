import axios from 'axios';

import { getApiBaseUrl } from './baseUrl';

const API_BASE_URL = getApiBaseUrl();

const syncApi = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
  timeout: 15000,
});

syncApi.interceptors.response.use(
  (response) => response,
  async (error) => {
    const requestUrl = error.config?.url || '';
    if (error.response?.status === 401 && !error.config?._retry && !requestUrl.includes('/auth/refresh')) {
      error.config._retry = true;
      try {
        await syncApi.post('/auth/refresh');
        return syncApi(error.config);
      } catch {
        if (window.location.pathname !== '/login') {
          window.location.href = '/login';
        }
      }
    }
    return Promise.reject(error);
  }
);

export const selectDriveFolder = (payload) => syncApi.post('/sync/folder', payload);
export const connectDriveSync = () => syncApi.post('/sync/connect');
export const getSyncStatus = () => syncApi.get('/sync/status');
export const getPickerToken = () => syncApi.get('/sync/picker-token');
export const triggerSync = () => syncApi.post('/sync/trigger');
export const disconnectDriveSync = () => syncApi.delete('/sync/disconnect');
