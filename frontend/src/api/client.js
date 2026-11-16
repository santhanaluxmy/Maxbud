import { getAuthSession } from "../services/authApi.js";

import { apiUrl } from "./base.js";

export async function api(path, { method = "GET", data, signal, requestId } = {}) {
  const token = getAuthSession()?.token;
  if (!token) throw new Error("Please sign in to continue.");
  let response;
  try {
    response = await fetch(apiUrl(path), {
      method,
      signal,
      headers: {
        ...(requestId ? { "Idempotency-Key": requestId } : {}),
        Authorization: `Bearer ${token}`,
        ...(data !== undefined ? { "Content-Type": "application/json" } : {}),
      },
      ...(data !== undefined ? { body: JSON.stringify(data) } : {}),
    });
  } catch (error) {
    if (error?.name === "AbortError") throw error;
    throw new Error("Cannot reach the MaxBud backend. Check FastAPI on port 8000.", { cause: error });
  }
  const result = await response.json().catch(() => null);
  if (!response.ok) {
    if (response.status === 401) { logout(); window.location.assign("/login"); }
    const detail = result?.detail;
    const message = Array.isArray(detail)
      ? detail.map((item) => item?.msg || "Invalid input").join("; ")
      : typeof detail === "string" ? detail : `Request failed (${response.status})`;
    const error = new Error(message);
    error.status = response.status;
    throw error;
  }
  return result;
}

export function money(value, currency = "LKR") {
  const amount = Number(value ?? 0);
  return `${currency} ${Number.isFinite(amount) ? amount.toLocaleString("en-LK", { minimumFractionDigits: 0, maximumFractionDigits: 2 }) : "0"}`;
}

export function logout() {
  sessionStorage.removeItem("maxbud_auth");
  localStorage.removeItem("maxbud_auth");
}