import axios from 'axios';
import { API_BASE_URL } from './baseUrl';

const albumsApi = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
});

export const listAlbums = () => albumsApi.get('/albums');
export const createAlbum = (payload) => albumsApi.post('/albums', payload);
export const getAlbum = (albumId, params) => albumsApi.get(`/albums/${albumId}`, { params });
export const patchAlbum = (albumId, payload) => albumsApi.patch(`/albums/${albumId}`, payload);
export const deleteAlbum = (albumId) => albumsApi.delete(`/albums/${albumId}`);
export const addAlbumPhotos = (albumId, payload) => albumsApi.post(`/albums/${albumId}/photos`, payload);
export const removeAlbumPhoto = (albumId, photoId) => albumsApi.delete(`/albums/${albumId}/photos/${photoId}`);
export const enableAlbumShare = (albumId) => albumsApi.post(`/albums/${albumId}/share`);
export const disableAlbumShare = (albumId) => albumsApi.delete(`/albums/${albumId}/share`);
