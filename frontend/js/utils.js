/**
 * SkillSync LMS — Utility Functions
 */

// ── Date / time ──────────────────────────────────────────────────────
export function formatDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export function formatDateTime(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatDuration(seconds) {
  if (seconds == null || seconds <= 0) return "0 min";
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const mins = Math.floor(seconds / 60);
  if (mins < 60) return `${mins} min`;
  const hrs = Math.floor(mins / 60);
  const rem = mins % 60;
  return rem > 0 ? `${hrs}h ${rem}m` : `${hrs}h`;
}

// ── HTML safety ──────────────────────────────────────────────────────
const ESC_MAP = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };

export function escapeHtml(str) {
  if (str == null) return "";
  return String(str).replace(/[&<>"']/g, (c) => ESC_MAP[c]);
}

// ── Toast notifications ─────────────────────────────────────────────
let toastContainer = null;

function ensureToastContainer() {
  if (toastContainer) return toastContainer;
  toastContainer = document.createElement("div");
  toastContainer.id = "toast-container";
  Object.assign(toastContainer.style, {
    position: "fixed",
    bottom: "1.5rem",
    right: "1.5rem",
    zIndex: "9999",
    display: "flex",
    flexDirection: "column",
    gap: "0.5rem",
    maxWidth: "380px",
  });
  document.body.appendChild(toastContainer);
  return toastContainer;
}

/**
 * Show a brief toast message.
 * @param {string} message
 * @param {"success"|"error"|"info"} [type="info"]
 * @param {number} [durationMs=3000]
 */
export function showToast(message, type = "info", durationMs = 3000) {
  const container = ensureToastContainer();
  const el = document.createElement("div");
  const colors = {
    success: { bg: "#d1fae5", border: "#10b981", color: "#065f46" },
    error: { bg: "#fee2e2", border: "#ef4444", color: "#991b1b" },
    info: { bg: "#e0e7ff", border: "#4f46e5", color: "#3730a3" },
  };
  const c = colors[type] || colors.info;
  Object.assign(el.style, {
    padding: "0.75rem 1rem",
    borderRadius: "8px",
    background: c.bg,
    borderLeft: `4px solid ${c.border}`,
    color: c.color,
    fontSize: "0.875rem",
    fontWeight: "500",
    boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1)",
    animation: "fadeIn 0.25s ease-in",
    cursor: "pointer",
  });
  el.textContent = message;
  el.addEventListener("click", () => el.remove());
  container.appendChild(el);
  setTimeout(() => {
    el.style.transition = "opacity 0.3s ease";
    el.style.opacity = "0";
    setTimeout(() => el.remove(), 300);
  }, durationMs);
}

// ── DOM helpers ──────────────────────────────────────────────────────
export function $(selector) {
  return document.querySelector(selector);
}

export function $$(selector) {
  return document.querySelectorAll(selector);
}

export function show(el) {
  if (typeof el === "string") el = $(el);
  if (el) el.style.display = "";
}

export function hide(el) {
  if (typeof el === "string") el = $(el);
  if (el) el.style.display = "none";
}

// ── Percent formatting ───────────────────────────────────────────────
export function pct(val) {
  if (val == null) return "—";
  return `${Math.round(val * 100) / 100}%`;
}

export function pctBar(val, max = 100) {
  const w = Math.min(100, Math.max(0, (val / max) * 100));
  return `<div class="progress-bar-container" style="height:6px"><div class="progress-bar" style="width:${w}%"></div></div>`;
}

// ── Risk badge ───────────────────────────────────────────────────────
export function riskBadge(level) {
  if (!level) return "";
  const cls = level === "high" ? "badge-danger" : level === "medium" ? "badge-warning" : "badge-success";
  return `<span class="badge ${cls}">${escapeHtml(level)}</span>`;
}

// ── Difficulty badge ─────────────────────────────────────────────────
export function diffBadge(d) {
  if (!d) return "";
  const cls = d === "hard" ? "badge-hard" : d === "medium" ? "badge-medium-diff" : "badge-easy";
  return `<span class="badge ${cls}">${escapeHtml(d)}</span>`;
}
