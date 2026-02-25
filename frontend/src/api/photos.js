import axios from 'axios';
import { API_BASE_URL } from './baseUrl';

const photoApi = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
});

export const getPhotoById = (photoId) => photoApi.get(`/photos/${photoId}`);
export const listPhotos = (params) => photoApi.get('/photos', { params });
export const getEmbeddingStatus = () => photoApi.get('/photos/embedding-status');
export const startEmbedding = () => photoApi.post('/photos/embedding/start');
export const listMapPhotos = () => photoApi.get('/photos/map');
export const exportPhotosArchive = () => photoApi.get('/photos/export', { responseType: 'blob' });
export const previewUploadPhotos = (formData) => photoApi.post('/photos/upload/preview', formData);
export const uploadPhotos = (formData, onUploadProgress) => photoApi.post('/photos/upload', formData, { onUploadProgress });
export const softDeletePhoto = (photoId) => photoApi.delete(`/photos/${photoId}`);
