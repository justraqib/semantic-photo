export function getApiBaseUrl() {
  const configured = import.meta.env.VITE_API_URL;
  if (configured && configured.trim().length > 0) {
    return configured;
  }

  if (typeof window !== 'undefined' && window.location?.hostname) {
    return `${window.location.protocol}//${window.location.hostname}:8000`;
  }

  return 'http://localhost:8000';
}
