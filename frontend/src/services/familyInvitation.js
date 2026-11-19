const KEY = "maxbud_invitation";
const validToken = token => typeof token === "string" && /^[A-Za-z0-9_-]{32,100}$/.test(token);

export function captureInvitation(hash) {
  if (!hash.startsWith("#invite=")) return false;
  let token = "";
  try { token = decodeURIComponent(hash.slice(8)); } catch { /* Show the invalid-link state. */ }
  if (validToken(token)) sessionStorage.setItem(KEY, token);
  else sessionStorage.removeItem(KEY);
  return true;
}

export function pendingInvitation() {
  const token = sessionStorage.getItem(KEY);
  return validToken(token) ? token : null;
}

export function clearInvitation() { sessionStorage.removeItem(KEY); }

export function authDestination(result) {
  if (pendingInvitation()) return "/invite";
  if (result.user?.role === "admin") return "/dashboard/admin";
  if (!result.onboarding_completed && result.has_household) return "/dashboard/family";
  return result.onboarding_completed ? "/dashboard" : "/onboarding";
}

export function invitationDate(value) {
  if (!value) return "Not recorded";
  const stamp = /(?:Z|[+-]\d{2}:\d{2})$/.test(value) ? value : value + "Z";
  return new Date(stamp).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}
