import { apiUrl } from "./base.js";

export async function publicPost(path, data, { signal } = {}) {
  let response;
  try {
    response = await fetch(apiUrl(path), {
      method: "POST", signal, cache: "no-store",
      headers: { "Content-Type": "application/json" }, body: JSON.stringify(data),
    });
  } catch (error) {
    if (error.name === "AbortError") throw error;
    throw new Error("MaxBud could not be reached. Please try again shortly.", { cause: error });
  }
  const result = await response.json().catch(() => null);
  if (!response.ok) {
    const error = new Error(typeof result?.detail === "string" ? result.detail : "The invitation could not be checked. Please try again.");
    error.status = response.status;
    throw error;
  }
  return result;
}
