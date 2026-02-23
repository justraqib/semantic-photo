import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const syncApi = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
});

export const selectDriveFolder = (payload) => syncApi.post('/sync/folder', payload);
