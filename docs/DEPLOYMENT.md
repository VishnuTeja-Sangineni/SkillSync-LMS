# SkillSync LMS — Cloud Deployment Guide

This guide describes how to configure, containerize, and deploy SkillSync LMS across production cloud environments.

---

## 1. Architecture Overview

SkillSync LMS follows the **12-Factor App** principles:
- **Stateless backend**: FastAPI handles all business logic, adaptive scoring, ML inference, and serves the static frontend.
- **Config via Environment**: No secrets or environment-specific URLs are hardcoded.
- **Database Agnostic**: Uses SQLAlchemy 2.x and Alembic to support local SQLite or cloud PostgreSQL with a single connection URL change.
- **Decoupled Model Storage**: Abstraction supports local disk or AWS S3 buckets.

```
       [ Client Browser ]
               │
               ▼
   [ Cloud Load Balancer / CDN ]
               │
               ▼
   [ FastAPI Backend Container ]
     ├── Serves Static SPA (/frontend)
     ├── REST API (/api/v1/*)
     └── In-Memory ML Predictor Cache
         │               │
         ▼               ▼
   [ PostgreSQL ]    [ AWS S3 / Volume ]
   (Managed DB)      (ML Artifacts)
```

---

## 2. Environment Variables Reference

| Variable | Type | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | string | `sqlite:///./skillsync.db` | SQLAlchemy connection URL. For PostgreSQL: `postgresql+psycopg://user:pass@host:5432/dbname` |
| `SECRET_KEY` | string | *required in prod* | Secret key for signing JWT tokens. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | int | `60` | JWT expiration duration in minutes. |
| `ENVIRONMENT` | string | `dev` | `dev` or `prod`. In `prod`, startup will validate that `SECRET_KEY` is not the default. |
| `AUTO_MIGRATE` | bool | `true` | Automatically run `alembic upgrade head` on startup. |
| `CORS_ORIGINS` | string | `*` | Comma-separated list of allowed origins (e.g. `https://my-lms.com`). |
| `PORT` | int | `8000` | Port for the Uvicorn web server. |
| `LOG_LEVEL` | string | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. |
| `MODEL_PATH` | string | `ml/artifacts/model.joblib` | Local path or S3 key for the trained ML model. |
| `MODEL_STORAGE` | string | `local` | `local` (filesystem) or `s3` (AWS S3 bucket). |
| `AWS_ACCESS_KEY_ID` | string | `""` | AWS credentials (only required if `MODEL_STORAGE=s3`). |
| `AWS_SECRET_ACCESS_KEY` | string | `""` | AWS credentials (only required if `MODEL_STORAGE=s3`). |
| `AWS_S3_BUCKET` | string | `""` | S3 bucket name for model artifacts. |
| `AWS_REGION` | string | `us-east-1` | AWS region. |

---

## 3. Database Setup (PostgreSQL)

When migrating from local SQLite to cloud PostgreSQL (e.g. AWS RDS, Neon, Supabase, Render PostgreSQL):

1. **Driver**: The application includes `psycopg` (v3). Use the `postgresql+psycopg://` URL scheme:
   ```env
   DATABASE_URL=postgresql+psycopg://skillsync_user:StrongPassword123@db.example.com:5432/skillsync
   ```
2. **SSL Mode**: Most cloud providers require SSL:
   ```env
   DATABASE_URL=postgresql+psycopg://skillsync_user:StrongPassword123@db.example.com:5432/skillsync?sslmode=require
   ```
3. **Automatic Migrations**: With `AUTO_MIGRATE=true`, Alembic applies any pending database migrations automatically during container startup.

---

## 4. Docker Deployment

### 4.1 Local / VM Multi-Container with Docker Compose
Run both the application and a dedicated PostgreSQL instance:
```bash
docker compose up --build -d
```
To view logs:
```bash
docker compose logs -f app
```

### 4.2 Building the Production Image
```bash
docker build -t skillsync-lms:latest .
```

### 4.3 Running Single Container
```bash
docker run -d \
  --name skillsync \
  -p 8000:8000 \
  -e DATABASE_URL="postgresql+psycopg://user:pass@host:5432/dbname" \
  -e SECRET_KEY="your-production-secret-key" \
  -e ENVIRONMENT="prod" \
  skillsync-lms:latest
```

---

## 5. Cloud Platform Deployments

### 5.1 Railway / Render
1. Connect your Git repository.
2. Add a managed PostgreSQL database.
3. Configure the environment variables:
   - `DATABASE_URL`: `${{Postgres.DATABASE_URL}}` (ensure the prefix is `postgresql+psycopg://`)
   - `SECRET_KEY`: Generate a random 64-character hex string.
   - `ENVIRONMENT`: `prod`
   - `AUTO_MIGRATE`: `true`
4. The repository includes a `Procfile` and `Dockerfile` which Railway and Render detect automatically.

### 5.2 AWS App Runner / Google Cloud Run
1. Push your built Docker container to AWS ECR or Google Artifact Registry.
2. Create an App Runner or Cloud Run service pointing to the container image.
3. Set container port to `8000`.
4. Configure health check path to `/api/v1/health`.
5. Inject environment variables for `DATABASE_URL` and `SECRET_KEY`.

---

## 6. Frontend Deployment Options

### Option A: Unified Deployment (Default & Recommended)
FastAPI automatically serves `frontend/index.html` and all static assets at `/`. No additional configuration is required.

### Option B: Standalone Frontend (Vercel / Netlify / S3 + CloudFront)
1. Deploy the `frontend/` folder to Vercel using the included `vercel.json`:
   ```bash
   vercel deploy
   ```
2. Update `frontend/js/config.js` to point to your deployed backend URL:
   ```javascript
   const API_BASE_URL = "https://api.skillsync-lms.com";
   export { API_BASE_URL };
   ```
3. On the backend, update `CORS_ORIGINS` to allow requests from your frontend domain:
   ```env
   CORS_ORIGINS=https://frontend.skillsync-lms.com
   ```

---

## 7. Model Storage in the Cloud (AWS S3)

To decouple trained ML models from container filesystem storage:

1. Create an S3 bucket (e.g. `skillsync-ml-artifacts`).
2. Set environment variables:
   ```env
   MODEL_STORAGE=s3
   AWS_S3_BUCKET=skillsync-ml-artifacts
   MODEL_PATH=models/production-model.joblib
   AWS_REGION=us-east-1
   AWS_ACCESS_KEY_ID=AKIA...
   AWS_SECRET_ACCESS_KEY=...
   ```
3. When admins click "Retrain Prediction Model" or run `POST /api/v1/admin/retrain`, the model is automatically serialized and streamed directly to S3.

---

## 8. Security & Production Checklist

- [ ] **Secret Key**: Generate a cryptographically secure key (`python -c "import secrets; print(secrets.token_hex(32))"`).
- [ ] **HTTPS / TLS**: Terminate TLS at the load balancer or reverse proxy.
- [ ] **Database Backups**: Enable automated daily snapshots on your managed PostgreSQL database.
- [ ] **CORS**: Restrict `CORS_ORIGINS` to trusted domains rather than `*`.
- [ ] **Health Monitoring**: Configure uptime monitors (Datadog, UptimeRobot, AWS CloudWatch) to ping `/api/v1/health` and `/api/v1/ready`.
