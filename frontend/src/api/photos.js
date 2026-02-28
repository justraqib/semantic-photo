import axios from 'axios';

import { getApiBaseUrl } from './baseUrl';

const API_BASE_URL = getApiBaseUrl();

const photoApi = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
  timeout: 15000,
});

photoApi.interceptors.response.use(
  (response) => response,
  async (error) => {
    const requestUrl = error.config?.url || '';
    if (error.response?.status === 401 && !error.config?._retry && !requestUrl.includes('/auth/refresh')) {
      error.config._retry = true;
      try {
        await photoApi.post('/auth/refresh');
        return photoApi(error.config);
      } catch {
        if (window.location.pathname !== '/login') {
          window.location.href = '/login';
        }
      }
    }
    return Promise.reject(error);
  }
);

export const getPhotoById = (photoId) => photoApi.get(`/photos/${photoId}`);
export const listPhotos = (params) => photoApi.get('/photos', { params });
export const getEmbeddingStatus = () => photoApi.get('/photos/embedding-status');
export const startEmbedding = () => photoApi.post('/photos/embedding/start');
export const listMapPhotos = () => photoApi.get('/photos/map');
export const listPeopleGroups = () => photoApi.get('/photos/meta/people');
export const getPeopleGroupPhotos = (groupId, params) => photoApi.get(`/photos/meta/people/${groupId}`, { params });
export const assignPeopleName = (payload) => photoApi.post('/photos/meta/people/assign', payload);
export const removeFromPeopleGroup = (payload) => photoApi.post('/photos/meta/people/remove', payload);
export const reindexPeopleGroups = (params) => photoApi.post('/photos/meta/people/reindex', null, { params });
export const listDuplicateGroups = () => photoApi.get('/photos/tools/duplicates');
export const deleteDuplicatePhotos = (payload) => photoApi.post('/photos/tools/duplicates/delete', payload);
export const deleteAllDuplicatePhotos = () => photoApi.post('/photos/tools/duplicates/delete-all');
export const exportPhotosArchive = () => photoApi.get('/photos/export', { responseType: 'blob' });
export const uploadPhotos = (formData, onUploadProgress) => photoApi.post('/photos/upload', formData, { onUploadProgress });
export const softDeletePhoto = (photoId) => photoApi.delete(`/photos/${photoId}`);
