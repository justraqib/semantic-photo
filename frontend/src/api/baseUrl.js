const envApiUrl = import.meta.env.VITE_API_URL;

function resolveApiBaseUrl() {
  if (typeof window !== 'undefined') {
    const currentHost = window.location.hostname;
    if (envApiUrl) {
      try {
        const parsed = new URL(envApiUrl);
        // If frontend is opened from LAN IP and env still points to localhost, rewrite host.
        if (
          currentHost !== "localhost" &&
          currentHost !== "127.0.0.1" &&
          (parsed.hostname === "localhost" || parsed.hostname === "127.0.0.1")
        ) {
          parsed.hostname = currentHost;
          return parsed.toString().replace(/\/$/, "");
        }
        return envApiUrl;
      } catch {
        return envApiUrl;
      }
    }
    return `${window.location.protocol}//${currentHost}:8000`;
  }
  if (typeof window === 'undefined') {
    return 'http://localhost:8000';
  }
  return envApiUrl || 'http://localhost:8000';
}

export const API_BASE_URL = resolveApiBaseUrl();
