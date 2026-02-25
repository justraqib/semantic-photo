import axios from 'axios';
import { API_BASE_URL } from './baseUrl';

const syncApi = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
});

export const selectDriveFolder = (payload) => syncApi.post('/sync/folder', payload);
export const connectDriveSync = () => syncApi.post('/sync/connect');
export const getSyncStatus = () => syncApi.get('/sync/status');
export const getPickerToken = () => syncApi.get('/sync/picker-token');
export const triggerSync = () => syncApi.post('/sync/trigger');
export const disconnectDriveSync = () => syncApi.delete('/sync/disconnect');
