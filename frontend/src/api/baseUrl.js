const envApiUrl = import.meta.env.VITE_API_URL;

function resolveApiBaseUrl() {
  if (envApiUrl) {
    return envApiUrl;
  }
  if (typeof window === 'undefined') {
    return 'http://localhost:8000';
  }
  return `${window.location.protocol}//${window.location.hostname}:8000`;
}

export const API_BASE_URL = resolveApiBaseUrl();
