/**
 * SkillSync LMS — Authentication Module
 */

import { api, setToken, setUser, getUser, isLoggedIn } from "./api.js";
import { navigateTo } from "./router.js";
import { $, showToast } from "./utils.js";

export function initAuth() {
  const loginForm = $("#login-form");
  const registerForm = $("#register-form");

  // ── Login Submit ───────────────────────────────────────────────────
  if (loginForm) {
    loginForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const email = $("#login-email").value.trim();
      const password = $("#login-password").value;
      const submitBtn = $("#login-submit-btn");

      if (!email || !password) {
        showToast("Please enter email and password.", "error");
        return;
      }

      try {
        if (submitBtn) submitBtn.disabled = true;
        const res = await api.post("/api/v1/auth/login", { email, password });
        setToken(res.access_token);
        setUser(res.user);
        showToast(`Welcome back, ${res.user.name}!`, "success");

        redirectAfterLogin(res.user.role);
      } catch (err) {
        showToast(err.message || "Login failed.", "error");
      } finally {
        if (submitBtn) submitBtn.disabled = false;
      }
    });
  }

  // ── Register Submit ────────────────────────────────────────────────
  if (registerForm) {
    registerForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const name = $("#reg-name").value.trim();
      const email = $("#reg-email").value.trim();
      const password = $("#reg-password").value;
      const role = $("#reg-role").value;
      const submitBtn = $("#reg-submit-btn");

      if (!name || !email || !password) {
        showToast("Please fill in all required fields.", "error");
        return;
      }

      try {
        if (submitBtn) submitBtn.disabled = true;
        const res = await api.post("/api/v1/auth/register", { name, email, password, role });
        setToken(res.access_token);
        setUser(res.user);
        showToast("Account created successfully!", "success");

        redirectAfterLogin(res.user.role);
      } catch (err) {
        showToast(err.message || "Registration failed.", "error");
      } finally {
        if (submitBtn) submitBtn.disabled = false;
      }
    });
  }

  // ── Quick-fill demo account buttons ────────────────────────────────
  document.querySelectorAll("[data-demo-user]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const type = btn.dataset.demoUser;
      const emailInput = $("#login-email");
      const passInput = $("#login-password");
      if (!emailInput || !passInput) return;

      if (type === "admin") {
        emailInput.value = "admin@skillsync.com";
        passInput.value = "Admin@123";
      } else if (type === "teacher") {
        emailInput.value = "teacher@skillsync.com";
        passInput.value = "Teacher@123";
      } else if (type === "student") {
        emailInput.value = "student@skillsync.com";
        passInput.value = "Student@123";
      }
    });
  });

  // ── Switch between login and register views ────────────────────────
  const toRegisterBtn = $("#to-register-btn");
  if (toRegisterBtn) {
    toRegisterBtn.addEventListener("click", (e) => {
      e.preventDefault();
      navigateTo("register");
    });
  }

  const toLoginBtn = $("#to-login-btn");
  if (toLoginBtn) {
    toLoginBtn.addEventListener("click", (e) => {
      e.preventDefault();
      navigateTo("login");
    });
  }
}

export function redirectAfterLogin(role) {
  if (role === "admin") {
    navigateTo("admin-dashboard");
  } else if (role === "teacher") {
    navigateTo("teacher-dashboard");
  } else {
    navigateTo("student-dashboard");
  }
}
