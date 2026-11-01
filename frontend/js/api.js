/**
 * SkillSync LMS — API Fetch Wrapper
 *
 * Centralised HTTP client that:
 * - Reads JWT from localStorage
 * - Auto-adds Authorization header
 * - Handles 401 → redirect to login
 * - Returns parsed JSON (or null on 204)
 */

import { API_BASE_URL } from "./config.js";

// ── Token helpers ────────────────────────────────────────────────────
export function getToken() {
  return localStorage.getItem("ss_token");
}

export function setToken(token) {
  localStorage.setItem("ss_token", token);
}

export function removeToken() {
  localStorage.removeItem("ss_token");
}

export function getUser() {
  const raw = localStorage.getItem("ss_user");
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function setUser(user) {
  localStorage.setItem("ss_user", JSON.stringify(user));
}

export function removeUser() {
  localStorage.removeItem("ss_user");
}

export function isLoggedIn() {
  return !!getToken();
}

export function logout() {
  removeToken();
  removeUser();
}

// ── Core fetch wrapper ───────────────────────────────────────────────
/**
 * @param {string} path - e.g. "/api/v1/auth/login"
 * @param {RequestInit} [options]
 * @returns {Promise<any>}
 */
export async function apiFetch(path, options = {}) {
  const url = `${API_BASE_URL}${path}`;

  const headers = { ...(options.headers || {}) };
  const token = getToken();
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  if (options.body && !(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }

  const resp = await fetch(url, { ...options, headers });

  if (resp.status === 401) {
    logout();
    // Only redirect if we're not already on login
    if (typeof window !== "undefined" && window.__ssRouter) {
      window.__ssRouter("login");
    }
    throw new Error("Session expired. Please log in again.");
  }

  if (resp.status === 204) return null;

  const data = await resp.json();

  if (!resp.ok) {
    const msg = data.detail || JSON.stringify(data);
    throw new Error(msg);
  }

  return data;
}

// ── Convenience methods ──────────────────────────────────────────────
export const api = {
  get: (path) => apiFetch(path, { method: "GET" }),

  post: (path, body) =>
    apiFetch(path, {
      method: "POST",
      body: body != null ? JSON.stringify(body) : undefined,
    }),

  patch: (path, body) =>
    apiFetch(path, {
      method: "PATCH",
      body: body != null ? JSON.stringify(body) : undefined,
    }),

  put: (path, body) =>
    apiFetch(path, {
      method: "PUT",
      body: body != null ? JSON.stringify(body) : undefined,
    }),

  delete: (path) => apiFetch(path, { method: "DELETE" }),
};
