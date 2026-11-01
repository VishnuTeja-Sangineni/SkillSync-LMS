/**
 * SkillSync LMS — Chart.js Wrapper Helpers
 *
 * All functions expect a <canvas> element id and data arrays.
 * Chart.js is loaded via CDN in index.html.
 */

/* global Chart */

// Destroy existing chart on the same canvas to avoid stacking
const chartInstances = {};

function getCtx(canvasId) {
  const el = document.getElementById(canvasId);
  if (!el) return null;
  if (chartInstances[canvasId]) {
    chartInstances[canvasId].destroy();
    delete chartInstances[canvasId];
  }
  return el.getContext("2d");
}

function save(canvasId, chart) {
  chartInstances[canvasId] = chart;
  return chart;
}

// ── Mastery Radar ────────────────────────────────────────────────────
/**
 * @param {string} canvasId
 * @param {string[]} topics
 * @param {number[]} values  - 0-100
 */
export function createMasteryRadar(canvasId, topics, values) {
  const ctx = getCtx(canvasId);
  if (!ctx) return;
  return save(
    canvasId,
    new Chart(ctx, {
      type: "radar",
      data: {
        labels: topics.map((t) => (t.length > 18 ? t.slice(0, 16) + "…" : t)),
        datasets: [
          {
            label: "Mastery %",
            data: values,
            backgroundColor: "rgba(79, 70, 229, 0.15)",
            borderColor: "#4f46e5",
            borderWidth: 2,
            pointBackgroundColor: "#4f46e5",
            pointRadius: 4,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          r: {
            beginAtZero: true,
            max: 100,
            ticks: { stepSize: 25, display: false },
            pointLabels: { font: { size: 11 } },
          },
        },
        plugins: { legend: { display: false } },
      },
    })
  );
}

// ── Score Trend Line ─────────────────────────────────────────────────
/**
 * @param {string} canvasId
 * @param {{label: string, score: number}[]} attempts
 */
export function createScoreTrendLine(canvasId, attempts) {
  const ctx = getCtx(canvasId);
  if (!ctx) return;
  return save(
    canvasId,
    new Chart(ctx, {
      type: "line",
      data: {
        labels: attempts.map((a) => a.label),
        datasets: [
          {
            label: "Score",
            data: attempts.map((a) => a.score),
            borderColor: "#4f46e5",
            backgroundColor: "rgba(79, 70, 229, 0.1)",
            fill: true,
            tension: 0.3,
            pointRadius: 4,
            pointBackgroundColor: "#4f46e5",
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          y: { beginAtZero: true, max: 100, title: { display: true, text: "Score %" } },
        },
        plugins: { legend: { display: false } },
      },
    })
  );
}

// ── Score Distribution Bar ───────────────────────────────────────────
/**
 * @param {string} canvasId
 * @param {{label: string, count: number}[]} bins
 */
export function createScoreDistributionBar(canvasId, bins) {
  const ctx = getCtx(canvasId);
  if (!ctx) return;
  return save(
    canvasId,
    new Chart(ctx, {
      type: "bar",
      data: {
        labels: bins.map((b) => b.label),
        datasets: [
          {
            label: "Students",
            data: bins.map((b) => b.count),
            backgroundColor: "#818cf8",
            borderRadius: 4,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          y: { beginAtZero: true, title: { display: true, text: "# Students" } },
        },
        plugins: { legend: { display: false } },
      },
    })
  );
}

// ── Topic Mastery Horizontal Bars ────────────────────────────────────
/**
 * @param {string} canvasId
 * @param {{topic: string, mastery: number}[]} data
 */
export function createTopicMasteryBars(canvasId, data) {
  const ctx = getCtx(canvasId);
  if (!ctx) return;
  const colors = data.map((d) =>
    d.mastery >= 70 ? "#10b981" : d.mastery >= 40 ? "#f59e0b" : "#ef4444"
  );
  return save(
    canvasId,
    new Chart(ctx, {
      type: "bar",
      data: {
        labels: data.map((d) => (d.topic.length > 22 ? d.topic.slice(0, 20) + "…" : d.topic)),
        datasets: [
          {
            label: "Avg Mastery %",
            data: data.map((d) => d.mastery),
            backgroundColor: colors,
            borderRadius: 4,
          },
        ],
      },
      options: {
        indexAxis: "y",
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: { beginAtZero: true, max: 100 },
        },
        plugins: { legend: { display: false } },
      },
    })
  );
}

// ── Engagement Line (daily active minutes) ──────────────────────────
/**
 * @param {string} canvasId
 * @param {{date: string, value: number}[]} dailyData
 */
export function createEngagementLine(canvasId, dailyData) {
  const ctx = getCtx(canvasId);
  if (!ctx) return;
  return save(
    canvasId,
    new Chart(ctx, {
      type: "line",
      data: {
        labels: dailyData.map((d) => d.date),
        datasets: [
          {
            label: "Minutes",
            data: dailyData.map((d) => d.value),
            borderColor: "#06b6d4",
            backgroundColor: "rgba(6, 182, 212, 0.1)",
            fill: true,
            tension: 0.3,
            pointRadius: 2,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          y: { beginAtZero: true, title: { display: true, text: "Minutes" } },
        },
        plugins: { legend: { display: false } },
      },
    })
  );
}
