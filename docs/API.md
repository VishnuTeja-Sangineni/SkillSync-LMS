# SkillSync LMS — API Reference Documentation

All API endpoints are versioned with the `/api/v1` prefix. Interactive API documentation is also available interactively via Swagger UI at `/docs` and ReDoc at `/redoc`.

---

## Table of Contents
1. [Authentication & Authorization](#1-authentication--authorization)
2. [Health & Readiness](#2-health--readiness)
3. [Authentication Endpoints](#3-authentication-endpoints)
4. [Courses & Curriculum](#4-courses--curriculum)
5. [Lessons](#5-lessons)
6. [Questions Bank](#6-questions-bank)
7. [Quizzes & Adaptive Engine](#7-quizzes--adaptive-engine)
8. [Progress Tracking](#8-progress-tracking)
9. [Learning Analytics](#9-learning-analytics)
10. [Student Performance Predictions](#10-student-performance-predictions)
11. [Personalized Recommendations](#11-personalized-recommendations)
12. [Admin Console](#12-admin-console)

---

## 1. Authentication & Authorization

SkillSync LMS uses **JSON Web Tokens (JWT)** with the `HS256` signing algorithm.

Pass the bearer token in the `Authorization` header for protected endpoints:
```http
Authorization: Bearer <access_token>
```

### Roles and Permissions:
- `student`: Access to enrolled courses, lessons, adaptive quizzes, personal progress, personal analytics, predictions, and recommendations.
- `teacher`: Full CRUD over owned courses, modules, lessons, questions, and quizzes; cohort analytics and at-risk early warning reports for owned courses.
- `admin`: Superuser access to all courses, user management, platform-wide metrics, and ML model retraining.

---

## 2. Health & Readiness

### Liveness Probe
```http
GET /api/v1/health
```
- **Auth**: None
- **Response `200 OK`**:
```json
{
  "status": "healthy",
  "service": "skillsync-lms"
}
```

### Readiness Probe
```http
GET /api/v1/ready
```
- **Auth**: None
- **Response `200 OK`**:
```json
{
  "status": "ready",
  "database": "connected"
}
```

---

## 3. Authentication Endpoints

### Register User
```http
POST /api/v1/auth/register
```
- **Auth**: None
- **Request Body**:
```json
{
  "name": "Alex Student",
  "email": "alex@example.com",
  "password": "Password@123",
  "role": "student"
}
```
- **Response `201 Created`**:
```json
{
  "access_token": "eyJhbGciOi...",
  "token_type": "bearer",
  "user": {
    "id": 154,
    "name": "Alex Student",
    "email": "alex@example.com",
    "role": "student",
    "created_at": "2026-11-01T12:00:00Z"
  }
}
```

### Log In
```http
POST /api/v1/auth/login
```
- **Auth**: None
- **Request Body**:
```json
{
  "email": "student@skillsync.com",
  "password": "Student@123"
}
```
- **Response `200 OK`**:
```json
{
  "access_token": "eyJhbGciOi...",
  "token_type": "bearer",
  "user": {
    "id": 4,
    "name": "Student Demo",
    "email": "student@skillsync.com",
    "role": "student",
    "created_at": "2026-11-01T10:00:00Z"
  }
}
```

### Get Current User Profile
```http
GET /api/v1/auth/me
```
- **Auth**: Any authenticated user
- **Response `200 OK`**: `UserResponse`

---

## 4. Courses & Curriculum

### List All Courses
```http
GET /api/v1/courses
```
- **Auth**: Any authenticated user
- **Response `200 OK`**: `List[CourseResponse]`

### List Enrolled Courses
```http
GET /api/v1/courses/enrolled
```
- **Auth**: Any authenticated user
- **Response `200 OK`**: `List[CourseResponse]`

### Get Course Details (with Modules & Lessons)
```http
GET /api/v1/courses/{course_id}
```
- **Auth**: Any authenticated user
- **Response `200 OK`**:
```json
{
  "id": 1,
  "title": "Algebra Foundations",
  "description": "Master linear equations, inequalities, factoring, and functions.",
  "teacher_id": 2,
  "modules": [
    {
      "id": 1,
      "course_id": 1,
      "title": "Module 1: Equations & Expressions",
      "order": 1,
      "lessons": [
        {
          "id": 1,
          "module_id": 1,
          "title": "Linear Equations Basics",
          "content": "...",
          "topic": "Linear Equations",
          "est_minutes": 15,
          "order": 1
        }
      ]
    }
  ]
}
```

### Create Course
```http
POST /api/v1/courses
```
- **Auth**: Teacher or Admin
- **Request Body**: `{ "title": "New Course", "description": "Optional summary" }`
- **Response `201 Created`**: `CourseResponse`

### Enroll in Course
```http
POST /api/v1/courses/{course_id}/enroll
```
- **Auth**: Any authenticated user
- **Response `201 Created`**:
```json
{
  "id": 300,
  "student_id": 4,
  "course_id": 1,
  "enrolled_at": "2026-11-01T12:00:00Z"
}
```

### Create Course Module
```http
POST /api/v1/courses/{course_id}/modules
```
- **Auth**: Course teacher or Admin
- **Request Body**: `{ "title": "Module Title", "order": 1 }`
- **Response `201 Created`**: `ModuleResponse`

---

## 5. Lessons

### Create Lesson
```http
POST /api/v1/lessons
```
- **Auth**: Course teacher or Admin
- **Request Body**:
```json
{
  "module_id": 1,
  "title": "Solving Systems of Equations",
  "content": "Lesson instructional text...",
  "topic": "Linear Equations",
  "est_minutes": 20,
  "order": 2
}
```
- **Response `201 Created`**: `LessonResponse`

### Get Lesson Content
```http
GET /api/v1/lessons/{lesson_id}
```
- **Auth**: Any authenticated user
- **Response `200 OK`**: `LessonResponse`

---

## 6. Questions Bank

### Create Question
```http
POST /api/v1/questions
```
- **Auth**: Course teacher or Admin
- **Request Body**:
```json
{
  "course_id": 1,
  "topic": "Linear Equations",
  "difficulty": "medium",
  "text": "Solve for x: 3x - 7 = 14",
  "options_json": ["x = 5", "x = 7", "x = 9", "x = 21"],
  "correct_index": 1
}
```
- **Response `201 Created`**: `QuestionResponse`

### Query Questions
```http
GET /api/v1/questions?course_id=1&topic=Linear%20Equations&difficulty=medium
```
- **Auth**: Teacher or Admin
- **Response `200 OK`**: `List[QuestionResponse]`

---

## 7. Quizzes & Adaptive Engine

### Create Quiz
```http
POST /api/v1/quizzes
```
- **Auth**: Course teacher or Admin
- **Request Body**:
```json
{
  "course_id": 1,
  "module_id": 1,
  "title": "Equations Mastery Check",
  "question_ids": [1, 2, 3, 4, 5]
}
```
- **Response `201 Created`**: `QuizDetailResponse`

### Start Adaptive Quiz Attempt
```http
POST /api/v1/quizzes/{quiz_id}/start
```
- **Auth**: Enrolled student or Teacher/Admin
- **Response `201 Created`**:
```json
{
  "attempt_id": 1050,
  "quiz_id": 1,
  "student_id": 4,
  "started_at": "2026-11-01T12:00:00Z",
  "total_questions": 5
}
```

### Fetch Next Adaptive Question
```http
GET /api/v1/quizzes/{quiz_id}/next-question?attempt_id=1050
```
- **Auth**: Attempt owner, Teacher, Admin
- **Response `200 OK`**:
```json
{
  "question": {
    "id": 12,
    "course_id": 1,
    "topic": "Linear Equations",
    "difficulty": "medium",
    "text": "Solve for x: 2(x + 3) = 16",
    "options_json": ["x = 5", "x = 6", "x = 7", "x = 8"]
  },
  "attempt_id": 1050,
  "question_number": 1,
  "total_questions": 5,
  "is_complete": false
}
```

### Submit Answer (Instant Mastery Update)
```http
POST /api/v1/quizzes/{quiz_id}/answer
```
- **Auth**: Attempt owner, Teacher, Admin
- **Request Body**:
```json
{
  "attempt_id": 1050,
  "question_id": 12,
  "selected_index": 0,
  "time_taken_sec": 24
}
```
- **Response `200 OK`**:
```json
{
  "is_correct": true,
  "correct_index": 0,
  "new_mastery": 74.5,
  "topic": "Linear Equations",
  "difficulty": "medium"
}
```

### Finish Quiz Attempt
```http
POST /api/v1/quizzes/{quiz_id}/finish
```
- **Auth**: Attempt owner, Teacher, Admin
- **Request Body**: `{ "attempt_id": 1050 }`
- **Response `200 OK`**:
```json
{
  "attempt_id": 1050,
  "quiz_id": 1,
  "student_id": 4,
  "score": 4,
  "max_score": 5,
  "percentage": 80.0,
  "duration_sec": 135,
  "finished_at": "2026-11-01T12:03:00Z"
}
```

---

## 8. Progress Tracking

### Record Lesson Progress
```http
POST /api/v1/progress/lesson
```
- **Auth**: Enrolled student or Teacher/Admin
- **Request Body**:
```json
{
  "lesson_id": 1,
  "completed": true,
  "time_spent_sec": 420
}
```
- **Response `200 OK`**: `LessonProgressResponse`

### Get Lesson Progress
```http
GET /api/v1/progress/lesson/{lesson_id}
```
- **Auth**: Any authenticated user
- **Response `200 OK`**: `LessonProgressResponse`

---

## 9. Learning Analytics

### Student Analytics
```http
GET /api/v1/analytics/student/{student_id}?course_id={course_id}
```
- **Auth**: Own student profile, or Teacher/Admin
- **Response `200 OK`**:
```json
{
  "student_id": 4,
  "student_name": "Student Demo",
  "course_id": 1,
  "mastery_by_topic": [
    {
      "topic": "Linear Equations",
      "course_id": 1,
      "raw_mastery": 74.5,
      "mastery": 74.5,
      "updated_at": "2026-11-01T12:03:00Z"
    }
  ],
  "score_trend": {
    "slope": 1.25,
    "direction": "improving",
    "attempts": [
      {
        "attempt_id": 1020,
        "quiz_id": 1,
        "quiz_title": "Quiz 1",
        "score": 4,
        "max_score": 5,
        "percentage": 80.0,
        "duration_sec": 120,
        "date": "2026-10-28T14:00:00Z"
      }
    ]
  },
  "total_time_spent_sec": 14500,
  "streak_days": 4,
  "weak_areas": ["Factoring"],
  "completed_lessons_count": 8,
  "total_lessons_count": 10
}
```

### Cohort Analytics (Instructor View)
```http
GET /api/v1/analytics/course/{course_id}
```
- **Auth**: Course owner teacher, or Admin
- **Response `200 OK`**:
```json
{
  "course_id": 1,
  "course_title": "Algebra Foundations",
  "total_enrolled": 92,
  "avg_completion_pct": 68.4,
  "topic_masteries": [
    {
      "topic": "Linear Equations",
      "avg_mastery": 72.3,
      "student_count": 92
    }
  ],
  "score_distribution": [
    { "bin": "0-20%", "count": 2, "percentage": 2.2 },
    { "bin": "20-40%", "count": 8, "percentage": 8.7 },
    { "bin": "40-60%", "count": 20, "percentage": 21.7 },
    { "bin": "60-80%", "count": 42, "percentage": 45.7 },
    { "bin": "80-100%", "count": 20, "percentage": 21.7 }
  ],
  "engagement_over_time": [
    { "date": "2026-10-25", "active_students": 28 },
    { "date": "2026-10-26", "active_students": 35 }
  ]
}
```

---

## 10. Student Performance Predictions

### Predict Individual Student Score
```http
GET /api/v1/predictions/student/{student_id}/course/{course_id}
```
- **Auth**: Own student, course teacher, or Admin
- **Response `200 OK`**:
```json
{
  "id": 15,
  "student_id": 4,
  "course_id": 1,
  "predicted_score": 73.2,
  "risk_level": "Low",
  "top_factors_json": [
    { "feature": "total_time_spent", "importance": 0.278, "explanation": "High total study time (4.2 hours)" },
    { "feature": "avg_quiz_score", "importance": 0.247, "explanation": "Consistent quiz performance (78%)" },
    { "feature": "avg_mastery", "importance": 0.215, "explanation": "Strong average mastery across topics (74%)" }
  ],
  "created_at": "2026-11-01T12:00:00Z"
}
```

### Cohort At-Risk Report (Instructor Early Warning)
```http
GET /api/v1/predictions/at-risk/course/{course_id}
```
- **Auth**: Course teacher or Admin
- **Response `200 OK`**:
```json
[
  {
    "student_id": 42,
    "student_name": "Jordan Lee",
    "student_email": "jordan.lee@example.com",
    "course_id": 1,
    "predicted_score": 46.5,
    "risk_level": "High",
    "top_factors": ["Low quiz scores (avg 42%)", "Low study time (<1 hour)", "Declining quiz score trend"],
    "suggested_intervention": "Schedule 1-on-1 tutoring and assign foundational review modules"
  }
]
```

---

## 11. Personalized Recommendations

### Get Recommendations
```http
GET /api/v1/recommendations/student/{student_id}/course/{course_id}?limit=5&refresh=false
```
- **Auth**: Own student, course teacher, or Admin
- **Response `200 OK`**:
```json
[
  {
    "id": 81,
    "student_id": 4,
    "course_id": 1,
    "type": "lesson",
    "target_id": 3,
    "reason": "Your Factoring mastery is 36%. Successful peers improved significantly after reviewing Factoring Quadratics.",
    "priority": 1,
    "created_at": "2026-11-01T12:00:00Z"
  },
  {
    "id": 82,
    "student_id": 4,
    "course_id": 1,
    "type": "quiz",
    "target_id": 2,
    "reason": "Test your retention on Linear Equations with a medium-difficulty practice quiz.",
    "priority": 2,
    "created_at": "2026-11-01T12:00:00Z"
  }
]
```

---

## 12. Admin Console

### List Users
```http
GET /api/v1/admin/users?role=student&skip=0&limit=50
```
- **Auth**: Admin only
- **Response `200 OK`**: `List[UserResponse]`

### Update User Role
```http
PATCH /api/v1/admin/users/{user_id}
```
- **Auth**: Admin only
- **Request Body**: `{ "role": "teacher" }`
- **Response `200 OK`**: `UserResponse`

### Delete User
```http
DELETE /api/v1/admin/users/{user_id}
```
- **Auth**: Admin only (cannot delete own account)
- **Response `204 No Content`**

### Platform Statistics
```http
GET /api/v1/admin/stats
```
- **Auth**: Admin only
- **Response `200 OK`**:
```json
{
  "total_users": 153,
  "total_students": 150,
  "total_teachers": 2,
  "total_courses": 3,
  "total_enrollments": 289,
  "total_quiz_attempts": 1049
}
```

### Trigger ML Model Retraining
```http
POST /api/v1/admin/retrain
```
- **Auth**: Admin only
- **Response `200 OK`**:
```json
{
  "status": "success",
  "samples": 289,
  "metrics": {
    "mae": 6.40,
    "rmse": 7.76,
    "r2": 0.792
  },
  "feature_importances": {
    "total_time_spent": 0.278,
    "avg_quiz_score": 0.247,
    "avg_mastery": 0.215
  },
  "trained_at": "2026-11-01T12:00:00Z",
  "model_path": "ml/artifacts/model.joblib"
}
```
