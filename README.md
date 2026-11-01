# 🎓 SkillSync LMS — Adaptive Learning Platform

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com)
[![SQLAlchemy 2.0](https://img.shields.io/badge/SQLAlchemy-2.0-red.svg)](https://www.sqlalchemy.org)
[![scikit-learn](https://img.shields.io/badge/scikit--learn-1.5+-orange.svg)](https://scikit-learn.org)
[![Tests Passing](https://img.shields.io/badge/tests-125%20passed-brightgreen.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**SkillSync LMS** is an enterprise-grade Adaptive Learning Management System that personalizes education through **real-time learning analytics**, **machine learning student performance prediction**, and **intelligent hybrid recommendations**.

Designed to run locally with a single command and architected for cloud deployment (Docker, Kubernetes, AWS, Railway, Vercel) with environment configuration changes only.

---

## 🌟 Key Capabilities

- **🧠 Adaptive Quiz Engine**: Questions adjust in real-time according to student topic mastery. Mastery updates instantly on each response using weighted difficulty curves and exponential forgetting decay.
- **🔮 ML Performance Prediction**: Trained `GradientBoostingRegressor` model predicts course final scores ($R^2 \approx 0.79$, $\text{MAE} \approx 6.4\%$), classifies risk level (Low, Medium, High), and extracts top driving factors with plain-English explanations.
- **🧭 Hybrid Recommender**: Blends rule-based remediation (targeting weak topics, strong topics, inactivity) with collaborative filtering (cosine similarity on topic mastery vectors across successful peers).
- **📊 Interactive Visual Analytics**: Powered by Chart.js — Topic Mastery Radar charts, Score Trajectory trend lines, Cohort Mastery horizontal bars, Score Distribution histograms, and Daily Active Engagement tracking.
- **🛡️ Enterprise Role-Based Access Control**: Strict multi-tenant authorization for Students, Teachers, and Administrators with JWT bearer authentication.
- **☁️ Cloud-Ready 12-Factor Design**: Multi-stage Docker image, PostgreSQL and SQLite dual support via single `DATABASE_URL`, pluggable S3/local model storage, and health/readiness endpoints.

---

## ⚡ Quickstart (Local Development)

### 1. Prerequisites
- **Python 3.11+** installed
- Git (optional)

### 2. Setup Virtual Environment & Install Dependencies
```powershell
# Clone or navigate to the project directory
cd "SkillSync LMS"

# Create and activate virtual environment
python -m venv venv
.\venv\Scripts\activate   # On Linux/macOS: source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Initialize & Seed Database
The project includes a synthetic dataset generator simulating 150 students with hidden ability/engagement distributions across 3 comprehensive curriculums:
```powershell
# Run database migrations and seed realistic learning activity
python scripts/seed.py --reset
```

### 4. Train Prediction Model
```powershell
# Train initial GradientBoostingRegressor on seeded student data
python -m ml.train
```

### 5. Launch the Platform
```powershell
# Start the FastAPI server with live reload
uvicorn app.main:app --reload
```

Open your browser to:
👉 [**http://localhost:8000**](http://localhost:8000)

---

## 🔑 Demo Accounts

The database comes pre-seeded with three demo accounts for instant evaluation:

| Role | Email | Password | Primary Use Case |
|---|---|---|---|
| **Student** | `student@skillsync.com` | `Student@123` | Adaptive quizzes, topic mastery radar, predicted score, personalized recommendations |
| **Teacher** | `teacher@skillsync.com` | `Teacher@123` | Cohort mastery analytics, score distributions, and At-Risk Student Early Warning System |
| **Admin** | `admin@skillsync.com` | `Admin@123` | Platform analytics, user administration, and one-click ML model retraining |

*Tip: The login page includes one-click buttons to automatically fill credentials.*

---

## 🐳 Docker Deployment

Run the complete platform with a dedicated PostgreSQL 16 database using Docker Compose:

```bash
docker compose up --build
```

- Application & UI: [http://localhost:8000](http://localhost:8000)
- Interactive API Docs: [http://localhost:8000/docs](http://localhost:8000/docs)
- PostgreSQL: `localhost:5432`

---

## 🧪 Testing & Code Coverage

SkillSync LMS includes a comprehensive automated test suite with **125 unit and integration tests** covering the adaptive quiz engine, forgetting decay math, JWT authentication, permissions, CRUD flows, synthetic data seeding, ML feature extraction & prediction, collaborative filtering, and frontend asset delivery.

```powershell
# Run all tests
pytest -v

# Run tests with code coverage report
pytest --cov=app --cov=ml --cov=recommender --cov-report=term-missing
```

---

## 📂 Project Structure

```text
SkillSync LMS/
├── app/                           # FastAPI Backend Application
│   ├── main.py                    # App entry point, CORS, static file mount
│   ├── config.py                  # pydantic-settings environment configuration
│   ├── database.py                # SQLAlchemy engine & session factory
│   ├── security.py                # JWT auth, password hashing & access control
│   ├── logging_config.py          # Structured JSON logging & request tracing
│   ├── models/                    # SQLAlchemy ORM Models (User, Course, Quiz, Progress, etc.)
│   ├── schemas/                   # Pydantic v2 validation schemas
│   ├── routers/                   # API Route Controllers (/api/v1/*)
│   └── services/                  # Business Logic (Adaptive Quiz Engine, Decay Mastery, Analytics)
├── ml/                            # Machine Learning Pipeline
│   ├── features.py                # 10-feature extraction per student per course
│   ├── train.py                   # GradientBoostingRegressor training pipeline
│   ├── predict.py                 # Predictor with in-memory caching & factor explanations
│   ├── storage.py                 # Pluggable model storage (LocalFileStorage, S3Storage)
│   └── artifacts/                 # Serialized model artifacts (.joblib)
├── recommender/                   # Recommendation Engine
│   └── engine.py                  # Hybrid rule-based + collaborative filtering engine
├── frontend/                      # Responsive Single-Page Application (No build step)
│   ├── index.html                 # Semantic HTML5 SPA Shell
│   ├── css/
│   │   └── style.css              # Custom responsive CSS design system
│   └── js/
│       ├── config.js              # Configurable API base URL
│       ├── api.js                 # JWT-authenticated fetch wrapper
│       ├── router.js              # Hash-based client SPA router
│       ├── auth.js                # Auth forms & demo account shortcuts
│       ├── charts.js              # Chart.js visualization wrappers
│       ├── utils.js               # Formatting & toast notification helpers
│       └── app.js                 # View controllers & adaptive quiz runner
├── alembic/                       # Database Migration Scripts
├── scripts/                       # Synthetic Data Generation & Seeding Scripts
│   ├── generate_data.py           # Probabilistic data generator (150 students, noisy engagement)
│   └── seed.py                    # Idempotent DB seeder
├── tests/                         # Automated Pytest Suite (125 tests)
├── docs/                          # In-Depth Documentation
│   ├── DESIGN.md                  # Comprehensive architectural design specification
│   ├── API.md                     # Complete REST API reference
│   └── DEPLOYMENT.md              # Cloud deployment guide (AWS, Railway, Render, Vercel)
├── Dockerfile                     # Multi-stage production container specification
├── docker-compose.yml             # Multi-container orchestration (App + PostgreSQL)
├── Procfile                       # Cloud PaaS process definition
├── vercel.json                    # Standalone frontend deployment configuration
└── requirements.txt               # Pinned dependencies
```

---

## 📖 Further Documentation

- 📘 [**Architecture & Design Spec (`docs/DESIGN.md`)**](file:///d:/SkillSync%20LMS/docs/DESIGN.md): Detailed algorithm specifications for adaptive testing, mastery decay formulas, feature engineering, and collaborative filtering.
- 📙 [**REST API Reference (`docs/API.md`)**](file:///d:/SkillSync%20LMS/docs/API.md): Request and response schemas, error codes, and endpoint documentation.
- 📗 [**Cloud Deployment Guide (`docs/DEPLOYMENT.md`)**](file:///d:/SkillSync%20LMS/docs/DEPLOYMENT.md): Instructions for deploying to Railway, Render, AWS App Runner, Cloud Run, and Vercel.

---

## 📄 License

This project is licensed under the MIT License.
