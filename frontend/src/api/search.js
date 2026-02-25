import axios from 'axios';
import { API_BASE_URL } from './baseUrl';

const searchApi = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
});

export const searchPhotos = (query) =>
  searchApi.get('/search', {
    params: { q: query },
  });
