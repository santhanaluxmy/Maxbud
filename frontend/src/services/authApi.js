
import { apiUrl } from "../api/base.js";

async function request(path, data) {
  let response;

  try {
    response = await fetch(apiUrl(path), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(data),
    });
  } catch {
    throw new Error(
      "Cannot connect to MaxBud backend. Check if FastAPI is running."
    );
  }

  const result = await response.json().catch(() => ({}));

  if (!response.ok) {
    if (typeof result.detail === "string") {
      throw new Error(result.detail);
    }

    if (Array.isArray(result.detail)) {
      throw new Error(
        result.detail.map((item) => item.msg).join(". ")
      );
    }

    throw new Error(
      `Authentication request failed (${response.status}).`
    );
  }

  return result;
}

export function registerUser(data) {
  return request("/auth/register", data);
}

export function loginUser(data) {
  localStorage.removeItem("maxbud_auth");
  sessionStorage.removeItem("maxbud_auth");
  return request("/auth/login", data);
}

// Requires a FastAPI POST /auth/google endpoint.
// Backend must verify the Google ID token securely.
export function googleLogin(credential) {
  return request("/auth/google", {
    credential,
  });
}

export function saveAuthSession(result, remember = false) {
  const storage = remember ? localStorage : sessionStorage;

  localStorage.removeItem("maxbud_auth");
  sessionStorage.removeItem("maxbud_auth");

  storage.setItem(
    "maxbud_auth",
    JSON.stringify({
      token: result.access_token,
      user: result.user,
      onboarding_completed: result.onboarding_completed,
    })
  );
}

export function getAuthSession() {
  try {
    const stored =
      sessionStorage.getItem("maxbud_auth") ||
      localStorage.getItem("maxbud_auth");

    if (!stored) return null;
    const session = JSON.parse(stored);
    const parts = session.token?.split(".");
    if (parts?.length === 3) {
      const payload = JSON.parse(atob(parts[1].replace(/-/g, "+").replace(/_/g, "/")));
      if (!Number.isFinite(payload.exp) || payload.exp * 1000 <= Date.now()) {
        localStorage.removeItem("maxbud_auth"); sessionStorage.removeItem("maxbud_auth"); return null;
      }
    }
    return session;
  } catch {
    return null;
  }
}
