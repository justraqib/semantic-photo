import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const photoApi = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
});

export const getPhotoById = (photoId) => photoApi.get(`/photos/${photoId}`);
export const listPhotos = (params) => photoApi.get('/photos', { params });
export const uploadPhotos = (formData, onUploadProgress) => photoApi.post('/photos/upload', formData, { onUploadProgress });
export const softDeletePhoto = (photoId) => photoApi.delete(`/photos/${photoId}`);
