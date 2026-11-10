
import {
  registerUser,
  loginUser,
  getAuthSession,
  saveAuthSession,
} from "../services/authApi";

const API_URL = (
  import.meta.env.VITE_API_URL ||
  "http://127.0.0.1:8000"
).replace(/\/$/, "");

function getErrorMessage(result, status) {
  if (typeof result?.detail === "string") {
    return result.detail;
  }

  if (Array.isArray(result?.detail)) {
    return result.detail
      .map((item) => item.msg)
      .join(". ");
  }

  return `Request failed (${status})`;
}

export async function register({
  fullName,
  full_name,
  email,
  password,
  confirmPassword,
  confirm_password,
}) {
  const result = await registerUser({
    full_name: (full_name ?? fullName ?? "").trim(),
    email: email.trim().toLowerCase(),
    password,
    confirm_password:
      confirm_password ?? confirmPassword ?? "",
  });

  saveAuthSession(result, false);

  return result;
}

export async function login(email, password) {
  const result = await loginUser({
    email: email.trim().toLowerCase(),
    password,
  });

  saveAuthSession(result, false);

  return result.user;
}

export async function getCurrentUser() {
  const token = getAccessToken();

  if (!token) {
    throw new Error("Please sign in first.");
  }

  let response;

  try {
    response = await fetch(`${API_URL}/auth/me`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });
  } catch {
    throw new Error(
      "Cannot connect to MaxBud backend."
    );
  }

  const result = await response
    .json()
    .catch(() => ({}));

  if (!response.ok) {
    throw new Error(
      getErrorMessage(result, response.status)
    );
  }

  return result;
}

export function logout() {
  localStorage.removeItem("maxbud_auth");
  sessionStorage.removeItem("maxbud_auth");
}

export function getAccessToken() {
  return getAuthSession()?.token ?? null;
}
