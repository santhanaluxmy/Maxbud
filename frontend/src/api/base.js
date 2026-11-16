// Local development uses Vite's same-origin proxy. Deployments may supply an
// absolute HTTPS API URL or keep /api behind their own reverse proxy.
export function resolveApiBaseUrl(value) {
  return value?.trim().replace(/\/+$/, "") || "/api";
}

export const API_BASE_URL = resolveApiBaseUrl(
  import.meta.env?.VITE_API_URL || import.meta.env?.VITE_BACKEND_URL,
);

export function apiUrl(path) {
  return `${API_BASE_URL}/${path.replace(/^\/+/, "")}`;
}
