/**
 * SkillSync LMS — Configuration
 *
 * Single source of truth for the API base URL.
 * When served by FastAPI: leave as "" (same-origin).
 * When hosted separately (Vercel, S3, etc.): set the full backend URL.
 */
const API_BASE_URL = "";

export { API_BASE_URL };
