/**
 * SkillSync LMS — Client-side SPA Router
 *
 * Simple hash-based router that:
 * - Shows/hides <section data-view="..."> elements
 * - Updates active nav link
 * - Manages role-based visibility
 */

import { isLoggedIn, getUser, logout as apiLogout } from "./api.js";
import { $ } from "./utils.js";

let currentView = null;
let currentParams = {};

// ── Public API ───────────────────────────────────────────────────────
/**
 * Navigate to a view, optionally with params.
 * @param {string} view   e.g. "login", "student-dashboard", "course"
 * @param {Object} [params]  e.g. { id: 5 }
 */
export function navigateTo(view, params = {}) {
  currentView = view;
  currentParams = params;
  window.location.hash = view;
  render();
}

export function getParams() {
  return currentParams;
}

export function getCurrentView() {
  return currentView;
}

// ── Internal rendering ───────────────────────────────────────────────
function render() {
  const user = getUser();
  const loggedIn = isLoggedIn();

  // Show/hide sections
  document.querySelectorAll("[data-view]").forEach((el) => {
    el.classList.toggle("active", el.dataset.view === currentView);
  });

  // Show/hide nav links
  const navbar = $("#navbar");
  const navLoggedOut = $("#nav-logged-out");
  const navLoggedIn = $("#nav-logged-in");

  if (loggedIn && user) {
    if (navLoggedOut) navLoggedOut.style.display = "none";
    if (navLoggedIn) navLoggedIn.style.display = "flex";
    if (navbar) navbar.style.display = "";

    // Role-specific links
    document.querySelectorAll("[data-role]").forEach((el) => {
      const roles = el.dataset.role.split(",");
      el.style.display = roles.includes(user.role) ? "" : "none";
    });

    // User badge
    const badge = $("#user-badge-text");
    if (badge) badge.textContent = `${user.name} (${user.role})`;
  } else {
    if (navLoggedOut) navLoggedOut.style.display = "flex";
    if (navLoggedIn) navLoggedIn.style.display = "none";
  }

  // Active nav link
  document.querySelectorAll(".nav-link[data-nav]").forEach((el) => {
    el.classList.toggle("active", el.dataset.nav === currentView);
  });

  // Dispatch custom event so views can load data
  window.dispatchEvent(
    new CustomEvent("ss:navigate", { detail: { view: currentView, params: currentParams } })
  );
}

// ── Navigation guard ─────────────────────────────────────────────────
const PUBLIC_VIEWS = ["login", "register"];

function guardedNavigate(view, params = {}) {
  if (!isLoggedIn() && !PUBLIC_VIEWS.includes(view)) {
    return navigateTo("login");
  }
  if (isLoggedIn() && PUBLIC_VIEWS.includes(view)) {
    const user = getUser();
    const home =
      user.role === "admin"
        ? "admin-dashboard"
        : user.role === "teacher"
        ? "teacher-dashboard"
        : "student-dashboard";
    return navigateTo(home);
  }
  navigateTo(view, params);
}

// ── Initialization ───────────────────────────────────────────────────
export function initRouter() {
  // Expose router globally so api.js can redirect on 401
  window.__ssRouter = (view) => navigateTo(view);

  // Hash change handler
  window.addEventListener("hashchange", () => {
    const hash = window.location.hash.replace("#", "") || "login";
    guardedNavigate(hash, currentParams);
  });

  // Logout button
  const logoutBtn = $("#btn-logout");
  if (logoutBtn) {
    logoutBtn.addEventListener("click", (e) => {
      e.preventDefault();
      apiLogout();
      navigateTo("login");
    });
  }

  // Nav link clicks
  document.querySelectorAll(".nav-link[data-nav]").forEach((el) => {
    el.addEventListener("click", (e) => {
      e.preventDefault();
      guardedNavigate(el.dataset.nav);
    });
  });

  // Brand click → home
  const brand = $(".brand");
  if (brand) {
    brand.addEventListener("click", (e) => {
      e.preventDefault();
      if (isLoggedIn()) {
        const user = getUser();
        const home =
          user.role === "admin"
            ? "admin-dashboard"
            : user.role === "teacher"
            ? "teacher-dashboard"
            : "student-dashboard";
        navigateTo(home);
      } else {
        navigateTo("login");
      }
    });
  }

  // Initial route
  const initial = window.location.hash.replace("#", "") || "login";
  guardedNavigate(initial);
}
