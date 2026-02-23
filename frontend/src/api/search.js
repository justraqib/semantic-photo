import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const searchApi = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
});

export const searchPhotos = (query) =>
  searchApi.get('/search', {
    params: { q: query },
  });
