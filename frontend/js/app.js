/**
 * SkillSync LMS — Main Application Logic
 *
 * Implements views:
 * - Student Dashboard (analytics, predictions, recommendations, courses)
 * - Teacher Dashboard (course analytics, at-risk alerts, interventions)
 * - Admin Dashboard (platform stats, user list, ML retrain)
 * - Course Detail View (modules, lessons, quizzes, enrollment)
 * - Lesson View (content display, progress tracking, complete button)
 * - Quiz View (adaptive quiz engine: start -> question -> feedback -> next -> finish)
 */

import { api, getUser, isLoggedIn } from "./api.js";
import { initRouter, navigateTo, getParams } from "./router.js";
import { initAuth } from "./auth.js";
import {
  $,
  $$,
  escapeHtml,
  formatDate,
  formatDateTime,
  formatDuration,
  showToast,
  diffBadge,
  riskBadge,
} from "./utils.js";
import {
  createMasteryRadar,
  createScoreTrendLine,
  createScoreDistributionBar,
  createTopicMasteryBars,
  createEngagementLine,
} from "./charts.js";

// ── State ────────────────────────────────────────────────────────────
let activeStudentCourseId = null;
let activeTeacherCourseId = null;
let lessonTimer = null;
let lessonSeconds = 0;
let currentQuizState = null;

// ── Bootstrap ────────────────────────────────────────────────────────
window.addEventListener("DOMContentLoaded", () => {
  initAuth();
  initRouter();

  // Listen for navigation events
  window.addEventListener("ss:navigate", (e) => {
    const { view, params } = e.detail;
    handleViewActivation(view, params);
  });
});

async function handleViewActivation(view, params) {
  if (!isLoggedIn()) return;
  const user = getUser();

  switch (view) {
    case "student-dashboard":
      await loadStudentDashboard();
      break;
    case "teacher-dashboard":
      await loadTeacherDashboard();
      break;
    case "admin-dashboard":
      await loadAdminDashboard();
      break;
    case "course":
      if (params && params.id) {
        await loadCourseDetail(params.id);
      }
      break;
    case "lesson":
      if (params && params.id) {
        await loadLesson(params.id);
      }
      break;
    case "quiz":
      if (params && params.id) {
        await initQuiz(params.id);
      }
      break;
    case "courses-list":
      await loadAllCoursesList();
      break;
    default:
      break;
  }
}

// =====================================================================
// 1. STUDENT DASHBOARD
// =====================================================================
async function loadStudentDashboard() {
  const user = getUser();
  if (!user) return;

  try {
    // 1. Load enrolled courses first
    const enrolled = await api.get("/api/v1/courses/enrolled");
    renderStudentCourses(enrolled);

    if (enrolled.length > 0) {
      if (!activeStudentCourseId || !enrolled.some((c) => c.id === activeStudentCourseId)) {
        activeStudentCourseId = enrolled[0].id;
      }
      setupStudentCourseSelector(enrolled);
    } else {
      activeStudentCourseId = null;
      $("#student-course-select-wrap").style.display = "none";
    }

    // 2. Load general analytics for student
    const analyticsPath = activeStudentCourseId
      ? `/api/v1/analytics/student/${user.id}?course_id=${activeStudentCourseId}`
      : `/api/v1/analytics/student/${user.id}`;
    const analytics = await api.get(analyticsPath);
    renderStudentAnalytics(analytics);

    // 3. Load prediction and recommendations if we have an active course
    if (activeStudentCourseId) {
      loadStudentPrediction(user.id, activeStudentCourseId);
      loadStudentRecommendations(user.id, activeStudentCourseId);
    } else {
      $("#student-prediction-banner").style.display = "none";
      $("#student-recommendations-list").innerHTML = `
        <div class="card" style="text-align:center; padding: 2rem;">
          <p class="text-muted">You are not enrolled in any courses yet.</p>
          <button class="btn btn-primary" id="btn-browse-courses" style="margin-top: 1rem;">Browse Courses</button>
        </div>
      `;
      $("#btn-browse-courses")?.addEventListener("click", () => navigateTo("courses-list"));
    }
  } catch (err) {
    console.error("Failed to load student dashboard:", err);
    showToast("Error loading dashboard data: " + err.message, "error");
  }
}

function setupStudentCourseSelector(courses) {
  const wrap = $("#student-course-select-wrap");
  const select = $("#student-course-select");
  if (!wrap || !select) return;

  wrap.style.display = "flex";
  select.innerHTML = courses
    .map((c) => `<option value="${c.id}" ${c.id === activeStudentCourseId ? "selected" : ""}>${escapeHtml(c.title)}</option>`)
    .join("");

  select.onchange = (e) => {
    activeStudentCourseId = parseInt(e.target.value, 10);
    loadStudentDashboard();
  };
}

function renderStudentAnalytics(analytics) {
  // Stat cards
  $("#stat-streak").textContent = `${analytics.streak_days || 0} days`;
  $("#stat-time").textContent = formatDuration(analytics.total_time_spent_sec);

  const completed = analytics.completed_lessons_count || 0;
  const total = analytics.total_lessons_count || 0;
  $("#stat-lessons").textContent = `${completed} / ${total}`;

  // Average mastery calculation
  const topics = analytics.mastery_by_topic || [];
  let avgMastery = 0;
  if (topics.length > 0) {
    const sum = topics.reduce((acc, t) => acc + (t.mastery || 0), 0);
    avgMastery = Math.round(sum / topics.length);
  }
  $("#stat-mastery").textContent = `${avgMastery}%`;

  // Mastery Radar Chart
  if (topics.length > 0) {
    const topicLabels = topics.map((t) => t.topic);
    const topicVals = topics.map((t) => Math.round(t.mastery || 0));
    createMasteryRadar("chart-student-radar", topicLabels, topicVals);
  }

  // Score Trend Chart
  const trend = analytics.score_trend;
  if (trend && trend.attempts && trend.attempts.length > 0) {
    const attempts = trend.attempts.map((a, i) => ({
      label: `Quiz #${i + 1} (${a.quiz_title ? a.quiz_title.slice(0, 12) : "Quiz"})`,
      score: Math.round(a.percentage || 0),
    }));
    createScoreTrendLine("chart-student-trend", attempts);
  }
}

async function loadStudentPrediction(studentId, courseId) {
  const banner = $("#student-prediction-banner");
  if (!banner) return;

  try {
    const pred = await api.get(`/api/v1/predictions/student/${studentId}/course/${courseId}`);
    if (pred.status === "not_ready") {
      banner.style.display = "none";
      return;
    }

    banner.style.display = "block";
    const scoreVal = Math.round(pred.predicted_score || 0);
    const isNew = Array.isArray(pred.top_factors_json) && pred.top_factors_json.some(f => (typeof f === "object" && (f.factor === "new_enrollment" || f.description?.includes("Newly enrolled"))));

    if (isNew) {
      $("#pred-score-value").textContent = `${scoreVal}% (Course Baseline)`;
      $("#pred-risk-badge").className = "badge badge-info";
      $("#pred-risk-badge").textContent = "Awaiting Coursework";
      $("#pred-banner-desc").textContent = "Initial starting baseline. As you complete lessons and quizzes, your predicted score will personalize automatically.";
    } else {
      $("#pred-score-value").textContent = `${scoreVal}%`;
      $("#pred-risk-badge").className = `badge badge-${pred.risk_level || "low"}`;
      $("#pred-risk-badge").textContent = `${pred.risk_level} Risk`;
      $("#pred-banner-desc").textContent = "Calculated by the GradientBoostingRegressor model based on your study habits and mastery level.";
    }

    // Top factors
    const factorsContainer = $("#pred-factors");
    factorsContainer.innerHTML = "";
    if (pred.top_factors_json && Array.isArray(pred.top_factors_json)) {
      pred.top_factors_json.forEach((f) => {
        const text = typeof f === "object" && f !== null ? (f.description || f.explanation || f.factor || f.feature || JSON.stringify(f)) : f;
        const div = document.createElement("div");
        div.className = "factor-pill";
        div.innerHTML = `<strong>${escapeHtml(text)}</strong>`;
        factorsContainer.appendChild(div);
      });
    }
  } catch (err) {
    console.warn("Prediction unavailable:", err);
    banner.style.display = "none";
  }
}

async function loadStudentRecommendations(studentId, courseId) {
  const listEl = $("#student-recommendations-list");
  if (!listEl) return;

  try {
    const recs = await api.get(`/api/v1/recommendations/student/${studentId}/course/${courseId}`);
    if (!recs || recs.length === 0) {
      listEl.innerHTML = `<p class="text-muted" style="padding:1rem;">You're doing great! No urgent recommendations at this time.</p>`;
      return;
    }

    listEl.innerHTML = recs
      .map((r) => {
        let actionBtn = "";
        if (r.type === "quiz" && r.target_id) {
          actionBtn = `<button class="btn btn-primary btn-sm" onclick="window.__ssGoQuiz(${r.target_id})">Take Quiz</button>`;
        } else if (r.type === "lesson" && r.target_id) {
          actionBtn = `<button class="btn btn-secondary btn-sm" onclick="window.__ssGoLesson(${r.target_id})">Review Lesson</button>`;
        } else {
          actionBtn = `<span class="badge badge-info">Action Item</span>`;
        }

        return `
        <div class="rec-item">
          <div class="rec-info">
            <span class="rec-priority">${r.priority}</span>
            <div>
              <div style="font-weight:600; font-size:0.925rem; margin-bottom:0.2rem;">${escapeHtml(r.reason)}</div>
              <div style="font-size:0.75rem; color:var(--text-muted); text-transform:uppercase;">Type: ${escapeHtml(r.type)}</div>
            </div>
          </div>
          <div>${actionBtn}</div>
        </div>
      `;
      })
      .join("");
  } catch (err) {
    console.error("Failed to load recommendations:", err);
    listEl.innerHTML = `<p class="text-danger" style="padding:1rem;">Unable to load recommendations.</p>`;
  }
}

function renderStudentCourses(courses) {
  const container = $("#student-courses-grid");
  if (!container) return;

  if (courses.length === 0) {
    container.innerHTML = `
      <div class="card" style="grid-column: 1 / -1; text-align: center; padding: 2rem;">
        <p class="card-desc">You are not enrolled in any courses yet.</p>
        <button class="btn btn-primary" onclick="window.__ssGoBrowse()">Browse All Courses</button>
      </div>
    `;
    return;
  }

  container.innerHTML = courses
    .map(
      (c) => `
      <div class="card">
        <h3 class="card-title">${escapeHtml(c.title)}</h3>
        <p class="card-desc">${escapeHtml(c.description || "No description provided.")}</p>
        <div style="display: flex; gap: 0.5rem; margin-top: 1rem;">
          <button class="btn btn-primary btn-sm" onclick="window.__ssGoCourse(${c.id})">Open Course</button>
        </div>
      </div>
    `
    )
    .join("");
}

// Global hooks for inline onclicks
window.__ssGoQuiz = (id) => navigateTo("quiz", { id });
window.__ssGoLesson = (id) => navigateTo("lesson", { id });
window.__ssGoCourse = (id) => navigateTo("course", { id });
window.__ssGoBrowse = () => navigateTo("courses-list");

// =====================================================================
// 2. TEACHER DASHBOARD
// =====================================================================
async function loadTeacherDashboard() {
  try {
    const courses = await api.get("/api/v1/courses");
    if (!courses || courses.length === 0) {
      $("#teacher-empty-state").style.display = "block";
      $("#teacher-dashboard-content").style.display = "none";
      return;
    }

    $("#teacher-empty-state").style.display = "none";
    $("#teacher-dashboard-content").style.display = "block";

    if (!activeTeacherCourseId || !courses.some((c) => c.id === activeTeacherCourseId)) {
      activeTeacherCourseId = courses[0].id;
    }

    setupTeacherCourseSelector(courses);
    await loadTeacherCourseData(activeTeacherCourseId);
  } catch (err) {
    console.error("Failed to load teacher dashboard:", err);
    showToast("Error loading teacher dashboard: " + err.message, "error");
  }
}

function setupTeacherCourseSelector(courses) {
  const select = $("#teacher-course-select");
  if (!select) return;

  select.innerHTML = courses
    .map((c) => `<option value="${c.id}" ${c.id === activeTeacherCourseId ? "selected" : ""}>${escapeHtml(c.title)}</option>`)
    .join("");

  select.onchange = (e) => {
    activeTeacherCourseId = parseInt(e.target.value, 10);
    loadTeacherCourseData(activeTeacherCourseId);
  };
}

async function loadTeacherCourseData(courseId) {
  try {
    // 1. Course Analytics
    const analytics = await api.get(`/api/v1/analytics/course/${courseId}`);
    $("#t-stat-enrolled").textContent = analytics.total_enrolled || 0;
    $("#t-stat-completion").textContent = `${Math.round(analytics.avg_completion_pct || 0)}%`;

    // Topic mastery bars
    if (analytics.topic_masteries && analytics.topic_masteries.length > 0) {
      const barData = analytics.topic_masteries.map((tm) => ({
        topic: tm.topic,
        mastery: Math.round(tm.avg_mastery || 0),
      }));
      createTopicMasteryBars("chart-teacher-topic-mastery", barData);
    }

    // Score distribution bars
    if (analytics.score_distribution && analytics.score_distribution.length > 0) {
      const distData = analytics.score_distribution.map((sd) => ({
        label: sd.bin,
        count: sd.count,
      }));
      createScoreDistributionBar("chart-teacher-score-dist", distData);
    }

    // Engagement line
    if (analytics.engagement_over_time && analytics.engagement_over_time.length > 0) {
      const engData = analytics.engagement_over_time.map((eo) => ({
        date: eo.date,
        value: eo.active_students,
      }));
      createEngagementLine("chart-teacher-engagement", engData);
    }

    // 2. At-risk students
    const atRisk = await api.get(`/api/v1/predictions/at-risk/course/${courseId}`);
    renderAtRiskTable(atRisk);
  } catch (err) {
    console.error("Failed to load teacher course data:", err);
    showToast("Error loading course analytics: " + err.message, "error");
  }
}

function renderAtRiskTable(students) {
  const tbody = $("#teacher-at-risk-tbody");
  if (!tbody) return;

  if (!students || students.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; padding: 2rem; color:var(--text-muted);">No students identified at risk in this course.</td></tr>`;
    return;
  }

  tbody.innerHTML = students
    .map((s) => {
      const factors = (s.top_factors || [])
        .map((f) => {
          const text = typeof f === "object" && f !== null ? (f.description || f.explanation || f.factor || f.feature || JSON.stringify(f)) : f;
          const isNegative = typeof f === "object" && f !== null && f.impact === "negative";
          const bg = isNegative ? "#fee2e2" : "#f1f5f9";
          const color = isNegative ? "#991b1b" : "#475569";
          return `<span class="badge" style="background:${bg}; color:${color}; margin: 2px; display: inline-block;">${escapeHtml(text)}</span>`;
        })
        .join(" ");
      return `
        <tr>
          <td><strong>${escapeHtml(s.student_name)}</strong><br><small class="text-muted">${escapeHtml(s.student_email)}</small></td>
          <td>${riskBadge(s.risk_level)}</td>
          <td><strong>${Math.round(s.predicted_score)}%</strong></td>
          <td style="max-width: 320px;">${factors || "—"}</td>
          <td><em>${escapeHtml(s.suggested_intervention || "Monitor progress")}</em></td>
          <td>
            <button class="btn btn-secondary btn-sm" onclick="window.__ssIntervene('${escapeHtml(s.student_email)}')">Contact</button>
          </td>
        </tr>
      `;
    })
    .join("");
}

window.__ssIntervene = (email) => {
  showToast(`Intervention notice prepared for: ${email}`, "info");
};

// =====================================================================
// 3. ADMIN DASHBOARD
// =====================================================================
async function loadAdminDashboard() {
  try {
    // 1. Stats
    const stats = await api.get("/api/v1/admin/stats");
    $("#admin-total-users").textContent = stats.total_users || 0;
    $("#admin-total-students").textContent = stats.total_students || 0;
    $("#admin-total-teachers").textContent = stats.total_teachers || 0;
    $("#admin-total-courses").textContent = stats.total_courses || 0;
    $("#admin-total-enrollments").textContent = stats.total_enrollments || 0;
    $("#admin-total-attempts").textContent = stats.total_quiz_attempts || 0;

    // 2. Users table
    loadAdminUsers();

    // 3. Retrain Button
    const retrainBtn = $("#btn-admin-retrain");
    if (retrainBtn) {
      retrainBtn.onclick = async () => {
        try {
          retrainBtn.disabled = true;
          retrainBtn.textContent = "Retraining Model...";
          const res = await api.post("/api/v1/admin/retrain");
          showToast(`Retraining complete! Samples: ${res.samples}, MAE: ${res.metrics?.mae?.toFixed(2) || "N/A"}`, "success");
        } catch (err) {
          showToast("Retraining failed: " + err.message, "error");
        } finally {
          retrainBtn.disabled = false;
          retrainBtn.textContent = "Retrain Prediction Model";
        }
      };
    }
  } catch (err) {
    console.error("Failed to load admin dashboard:", err);
    showToast("Error loading admin stats: " + err.message, "error");
  }
}

async function loadAdminUsers() {
  const tbody = $("#admin-users-tbody");
  if (!tbody) return;

  try {
    const users = await api.get("/api/v1/admin/users?limit=50");
    tbody.innerHTML = users
      .map(
        (u) => `
        <tr>
          <td>#${u.id}</td>
          <td><strong>${escapeHtml(u.name)}</strong></td>
          <td>${escapeHtml(u.email)}</td>
          <td><span class="badge ${u.role === "admin" ? "badge-danger" : u.role === "teacher" ? "badge-warning" : "badge-info"}">${escapeHtml(u.role)}</span></td>
          <td>${formatDate(u.created_at)}</td>
          <td>
            <button class="btn btn-danger btn-sm" onclick="window.__ssDeleteUser(${u.id})">Delete</button>
          </td>
        </tr>
      `
      )
      .join("");
  } catch (err) {
    console.error("Failed to load users:", err);
  }
}

window.__ssDeleteUser = async (userId) => {
  if (!confirm(`Are you sure you want to delete user #${userId}?`)) return;
  try {
    await api.delete(`/api/v1/admin/users/${userId}`);
    showToast("User deleted successfully.", "success");
    loadAdminUsers();
  } catch (err) {
    showToast("Error deleting user: " + err.message, "error");
  }
};

// =====================================================================
// 4. COURSE DETAIL VIEW
// =====================================================================
async function loadCourseDetail(courseId) {
  try {
    const course = await api.get(`/api/v1/courses/${courseId}`);
    $("#course-detail-title").textContent = course.title;
    $("#course-detail-desc").textContent = course.description || "No description.";

    // Check enrollment
    const enrolled = await api.get("/api/v1/courses/enrolled");
    const isEnrolled = enrolled.some((c) => c.id === course.id);
    const enrollBtn = $("#btn-course-enroll");
    if (enrollBtn) {
      if (isEnrolled) {
        enrollBtn.textContent = "Enrolled";
        enrollBtn.disabled = true;
      } else {
        enrollBtn.textContent = "Enroll in Course";
        enrollBtn.disabled = false;
        enrollBtn.onclick = async () => {
          try {
            enrollBtn.disabled = true;
            await api.post(`/api/v1/courses/${courseId}/enroll`);
            showToast("Successfully enrolled!", "success");
            loadCourseDetail(courseId);
          } catch (err) {
            showToast("Enrollment failed: " + err.message, "error");
            enrollBtn.disabled = false;
          }
        };
      }
    }

    // Render Modules & Lessons
    const modulesContainer = $("#course-modules-list");
    if (modulesContainer) {
      if (!course.modules || course.modules.length === 0) {
        modulesContainer.innerHTML = `<p class="text-muted">No modules available yet.</p>`;
      } else {
        modulesContainer.innerHTML = course.modules
          .map(
            (m) => `
            <div class="card" style="margin-bottom: 1rem;">
              <h4 style="font-weight:600; margin-bottom: 0.75rem;">${escapeHtml(m.title)}</h4>
              <div style="display: flex; flex-direction: column; gap: 0.5rem;">
                ${(m.lessons || [])
                  .map(
                    (l) => `
                    <div style="display: flex; justify-content: space-between; align-items: center; padding: 0.5rem 0; border-bottom: 1px solid var(--border);">
                      <div>
                        <strong>${escapeHtml(l.title)}</strong>
                        <span style="font-size: 0.75rem; color: var(--text-muted); margin-left: 0.5rem;">(${l.est_minutes || 10} min)</span>
                      </div>
                      <button class="btn btn-secondary btn-sm" onclick="window.__ssGoLesson(${l.id})">Study</button>
                    </div>
                  `
                  )
                  .join("")}
              </div>
            </div>
          `
          )
          .join("");
      }
    }

    // Render Quizzes
    const quizzes = await api.get(`/api/v1/quizzes?course_id=${courseId}`);
    const quizzesContainer = $("#course-quizzes-list");
    if (quizzesContainer) {
      if (!quizzes || quizzes.length === 0) {
        quizzesContainer.innerHTML = `<p class="text-muted">No quizzes available for this course.</p>`;
      } else {
        quizzesContainer.innerHTML = quizzes
          .map(
            (q) => `
            <div style="display: flex; justify-content: space-between; align-items: center; padding: 0.75rem; border: 1px solid var(--border); border-radius: var(--radius-md); margin-bottom: 0.5rem; background: #fff;">
              <div>
                <strong>${escapeHtml(q.title)}</strong>
              </div>
              <button class="btn btn-primary btn-sm" onclick="window.__ssGoQuiz(${q.id})">Start Quiz</button>
            </div>
          `
          )
          .join("");
      }
    }
  } catch (err) {
    console.error("Failed to load course details:", err);
    showToast("Error loading course: " + err.message, "error");
  }
}

async function loadAllCoursesList() {
  const container = $("#all-courses-grid");
  if (!container) return;

  try {
    const courses = await api.get("/api/v1/courses");
    container.innerHTML = courses
      .map(
        (c) => `
        <div class="card">
          <h3 class="card-title">${escapeHtml(c.title)}</h3>
          <p class="card-desc">${escapeHtml(c.description || "No description.")}</p>
          <button class="btn btn-primary btn-sm" onclick="window.__ssGoCourse(${c.id})">View Course</button>
        </div>
      `
      )
      .join("");
  } catch (err) {
    showToast("Error loading courses: " + err.message, "error");
  }
}

// =====================================================================
// 5. LESSON VIEW
// =====================================================================
async function loadLesson(lessonId) {
  // Clear any existing lesson timer
  if (lessonTimer) clearInterval(lessonTimer);
  lessonSeconds = 0;

  try {
    const lesson = await api.get(`/api/v1/lessons/${lessonId}`);
    $("#lesson-title").textContent = lesson.title;
    $("#lesson-topic").textContent = lesson.topic ? `Topic: ${lesson.topic}` : "";
    $("#lesson-content").innerHTML = `<p>${escapeHtml(lesson.content || "Lesson content goes here.")}</p>`;

    // Start time tracker
    lessonTimer = setInterval(() => {
      lessonSeconds += 1;
      const el = $("#lesson-timer-display");
      if (el) el.textContent = formatDuration(lessonSeconds);
    }, 1000);

    // Complete button
    const completeBtn = $("#btn-complete-lesson");
    if (completeBtn) {
      completeBtn.disabled = false;
      completeBtn.onclick = async () => {
        try {
          completeBtn.disabled = true;
          await api.post("/api/v1/progress/lesson", {
            lesson_id: lesson.id,
            completed: true,
            time_spent_sec: lessonSeconds,
          });
          showToast("Lesson marked as completed!", "success");
        } catch (err) {
          showToast("Failed to record progress: " + err.message, "error");
          completeBtn.disabled = false;
        }
      };
    }
  } catch (err) {
    showToast("Error loading lesson: " + err.message, "error");
  }
}

// =====================================================================
// 6. ADAPTIVE QUIZ VIEW
// =====================================================================
async function initQuiz(quizId) {
  $("#quiz-intro-box").style.display = "block";
  $("#quiz-question-container").style.display = "none";
  $("#quiz-results-box").style.display = "none";

  try {
    const quiz = await api.get(`/api/v1/quizzes/${quizId}`);
    $("#quiz-view-title").textContent = quiz.title;

    const startBtn = $("#btn-start-quiz");
    if (startBtn) {
      startBtn.onclick = async () => {
        try {
          startBtn.disabled = true;
          const attempt = await api.post(`/api/v1/quizzes/${quizId}/start`);
          currentQuizState = {
            quizId,
            attemptId: attempt.attempt_id,
            totalQuestions: attempt.total_questions || 5,
            currentQuestion: null,
            startTime: Date.now(),
          };
          $("#quiz-intro-box").style.display = "none";
          $("#quiz-question-container").style.display = "block";
          await fetchNextQuizQuestion();
        } catch (err) {
          showToast("Cannot start quiz: " + err.message, "error");
          startBtn.disabled = false;
        }
      };
    }
  } catch (err) {
    showToast("Error loading quiz: " + err.message, "error");
  }
}

async function fetchNextQuizQuestion() {
  if (!currentQuizState) return;

  // Reset feedback & buttons
  $("#quiz-feedback-box").style.display = "none";
  $("#btn-submit-answer").style.display = "inline-flex";
  $("#btn-submit-answer").disabled = true;
  $("#btn-next-question").style.display = "none";

  try {
    const next = await api.get(`/api/v1/quizzes/${currentQuizState.quizId}/next-question?attempt_id=${currentQuizState.attemptId}`);

    if (next.is_complete || !next.question) {
      // Quiz finished
      await finishQuiz();
      return;
    }

    currentQuizState.currentQuestion = next.question;
    currentQuizState.questionStartTime = Date.now();

    // Progress bar
    const qNum = next.question_number || 1;
    const total = next.total_questions || currentQuizState.totalQuestions;
    $("#quiz-question-number").textContent = `Question ${qNum} of ${total}`;
    const pct = ((qNum - 1) / total) * 100;
    $("#quiz-progress-bar").style.width = `${pct}%`;

    // Render Question
    const q = next.question;
    $("#quiz-question-text").textContent = q.text;
    $("#quiz-question-topic").textContent = q.topic || "";
    $("#quiz-question-diff").innerHTML = diffBadge(q.difficulty);

    // Options
    const optionsBox = $("#quiz-options-list");
    optionsBox.innerHTML = "";
    let selectedIndex = null;

    q.options_json.forEach((optText, idx) => {
      const optDiv = document.createElement("div");
      optDiv.className = "option-item";
      optDiv.innerHTML = `<strong>${String.fromCharCode(65 + idx)}.</strong>&nbsp;&nbsp;${escapeHtml(optText)}`;
      optDiv.onclick = () => {
        if ($("#btn-submit-answer").style.display === "none") return; // already submitted
        $$(".option-item").forEach((el) => el.classList.remove("selected"));
        optDiv.classList.add("selected");
        selectedIndex = idx;
        $("#btn-submit-answer").disabled = false;
      };
      optionsBox.appendChild(optDiv);
    });

    // Wire submit
    $("#btn-submit-answer").onclick = async () => {
      if (selectedIndex === null) return;
      $("#btn-submit-answer").disabled = true;

      const timeTaken = Math.max(1, Math.round((Date.now() - currentQuizState.questionStartTime) / 1000));

      try {
        const ans = await api.post(`/api/v1/quizzes/${currentQuizState.quizId}/answer`, {
          attempt_id: currentQuizState.attemptId,
          question_id: q.id,
          selected_index: selectedIndex,
          time_taken_sec: timeTaken,
        });

        // Highlight options
        const optionEls = $$(".option-item");
        if (ans.is_correct) {
          optionEls[selectedIndex]?.classList.add("correct");
        } else {
          optionEls[selectedIndex]?.classList.add("wrong");
          if (ans.correct_index != null) {
            optionEls[ans.correct_index]?.classList.add("correct");
          }
        }

        // Show feedback
        const fbBox = $("#quiz-feedback-box");
        fbBox.style.display = "block";
        fbBox.className = `feedback-banner ${ans.is_correct ? "badge-success" : "badge-danger"}`;
        fbBox.innerHTML = `
          <strong>${ans.is_correct ? "✓ Correct!" : "✗ Incorrect."}</strong>
          <div>New topic mastery: <strong>${Math.round(ans.new_mastery || 0)}%</strong></div>
        `;

        // Switch to Next button
        $("#btn-submit-answer").style.display = "none";
        $("#btn-next-question").style.display = "inline-flex";
        $("#btn-next-question").onclick = () => fetchNextQuizQuestion();
      } catch (err) {
        showToast("Error submitting answer: " + err.message, "error");
        $("#btn-submit-answer").disabled = false;
      }
    };
  } catch (err) {
    showToast("Error retrieving question: " + err.message, "error");
  }
}

async function finishQuiz() {
  if (!currentQuizState) return;

  try {
    const res = await api.post(`/api/v1/quizzes/${currentQuizState.quizId}/finish`, {
      attempt_id: currentQuizState.attemptId,
    });

    $("#quiz-question-container").style.display = "none";
    $("#quiz-results-box").style.display = "block";

    const pctVal = Math.round(res.percentage || 0);
    $("#quiz-final-score").textContent = `${res.score} / ${res.max_score} (${pctVal}%)`;
    $("#quiz-final-duration").textContent = formatDuration(res.duration_sec);

    $("#btn-quiz-return-dashboard").onclick = () => {
      navigateTo("student-dashboard");
    };
  } catch (err) {
    showToast("Error finishing quiz: " + err.message, "error");
  }
}
