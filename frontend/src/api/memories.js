import axios from 'axios';
import { API_BASE_URL } from './baseUrl';

const memoriesApi = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
});

export const getTodayMemory = () => memoriesApi.get('/memories');
