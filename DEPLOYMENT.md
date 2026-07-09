# Saral — Deployment Guide

This guide covers deploying Saral to **Render** (recommended for free hosting) and optionally to **IBM Cloud Code Engine**.

---

## Option 1: Render (Recommended for Internship Submission)

Render provides a free tier for web services that is sufficient for demonstrating Saral.

### Prerequisites

- A [Render account](https://render.com) (free)
- Your IBM watsonx.ai credentials
- Your project pushed to GitHub or GitLab

### Step 1: Prepare the project

Create a `Procfile` in the project root:

```
web: gunicorn --bind 0.0.0.0:$PORT --workers 1 --timeout 120 app:application
```

Add `gunicorn` to `requirements.txt`:

```
gunicorn==21.2.0
```

> **Important:** Add `chromadb/` and `uploads/` and `instance/` to `.gitignore` — these are created at runtime.

### Step 2: Create `.gitignore`

```gitignore
# Environment
.env
venv/
__pycache__/
*.pyc

# Runtime data (created on start)
instance/
uploads/
vectordb/

# Dev logs
flask_stdout.txt
flask_stderr.txt

# OS
.DS_Store
Thumbs.db
```

### Step 3: Push to GitHub

```bash
git init
git add .
git commit -m "Initial commit — Saral AI educational assistant"
git remote add origin https://github.com/your-username/SaraL.git
git push -u origin main
```

### Step 4: Create a Render Web Service

1. Go to [render.com/dashboard](https://render.com/dashboard)
2. Click **New → Web Service**
3. Connect your GitHub repository
4. Configure the service:
   - **Name:** `saral-app`
   - **Region:** Singapore (closest to au-syd IBM endpoint)
   - **Branch:** `main`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn --bind 0.0.0.0:$PORT --workers 1 --timeout 120 app:application`
   - **Plan:** Free

### Step 5: Set Environment Variables on Render

In the Render dashboard → **Environment** tab, add:

| Key | Value |
|---|---|
| `WATSONX_API_KEY` | Your IBM Cloud API key |
| `WATSONX_PROJECT_ID` | Your watsonx.ai project ID |
| `WATSONX_URL` | `https://au-syd.ml.cloud.ibm.com` |
| `WATSONX_MODEL_ID` | `meta-llama/llama-3-3-70b-instruct` |
| `FLASK_SECRET_KEY` | A long random string (e.g., `openssl rand -hex 32`) |
| `FLASK_DEBUG` | `false` |
| `MAX_UPLOAD_SIZE_MB` | `10` |
| `RATE_LIMIT_PER_MINUTE` | `3` |
| `RATE_LIMIT_PER_DAY` | `30` |

> **Security:** Never commit `.env` to GitHub. Always set secrets via the Render dashboard.

### Step 6: Deploy

Click **Deploy**. The first build installs dependencies and downloads the `all-MiniLM-L6-v2` model (~90 MB). This takes 3–5 minutes.

Once deployed, your app will be available at `https://saral-app.onrender.com`.

### Render Limitations (Free Tier)

| Limitation | Impact |
|---|---|
| Spins down after 15 min inactivity | Cold start ~30s |
| 512 MB RAM | Sufficient for 1–2 concurrent users |
| Ephemeral disk | ChromaDB and uploads reset on redeploy |
| No persistent storage | Documents must be re-uploaded after restart |

> **For the internship demonstration**, this is perfectly acceptable. For production, upgrade to a paid Render plan or use IBM Cloud (below).

---

## Option 2: IBM Cloud Code Engine

IBM Cloud Code Engine provides container-based deployment and is the natural production target for an IBM watsonx.ai project.

### Step 1: Create a `Dockerfile`

```dockerfile
FROM python:3.10-slim

WORKDIR /app

# Install system dependencies for PyMuPDF
RUN apt-get update && apt-get install -y \
    libmupdf-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create runtime directories
RUN mkdir -p uploads instance vectordb

EXPOSE 8080

CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--timeout", "120", "app:application"]
```

### Step 2: Build and push to IBM Container Registry

```bash
# Install IBM Cloud CLI
curl -fsSL https://clis.cloud.ibm.com/install/linux | sh
ibmcloud login

# Build and push
ibmcloud cr namespace-add saral
docker build -t au.icr.io/saral/saral-app:latest .
docker push au.icr.io/saral/saral-app:latest
```

### Step 3: Deploy to Code Engine

```bash
ibmcloud ce project create --name saral-project
ibmcloud ce application create \
  --name saral-app \
  --image au.icr.io/saral/saral-app:latest \
  --env WATSONX_API_KEY=<your-key> \
  --env WATSONX_PROJECT_ID=<your-project-id> \
  --env FLASK_SECRET_KEY=<random-string> \
  --port 8080 \
  --min-scale 0 \
  --max-scale 1
```

---

## Production Checklist

Before submitting or deploying for evaluation:

- [ ] `FLASK_DEBUG=false` in production environment
- [ ] `FLASK_SECRET_KEY` is a strong random string (not the default)
- [ ] `.env` is in `.gitignore` (never committed)
- [ ] IBM API key has minimal permissions (watsonx.ai inference only)
- [ ] Rate limits configured appropriately (`RATE_LIMIT_PER_DAY=30` for Lite plan)
- [ ] Test all 6 features after deployment:
  - [ ] Upload a PDF
  - [ ] Ask Saral (chat)
  - [ ] Generate a Summary
  - [ ] Generate a Quiz
  - [ ] Simplify text + Regenerate
  - [ ] Explain a term
  - [ ] Generate Revision notes

---

## Environment Variables Reference

| Variable | Default | Description |
|---|---|---|
| `WATSONX_API_KEY` | *(required)* | IBM Cloud API key |
| `WATSONX_PROJECT_ID` | *(required)* | watsonx.ai project ID |
| `WATSONX_URL` | `https://au-syd.ml.cloud.ibm.com` | Region endpoint |
| `WATSONX_MODEL_ID` | `meta-llama/llama-3-3-70b-instruct` | Foundation model |
| `FLASK_SECRET_KEY` | `dev-secret-change-in-production` | Session key |
| `FLASK_DEBUG` | `false` | Debug mode |
| `MAX_UPLOAD_SIZE_MB` | `25` | Upload limit in MB |
| `RATE_LIMIT_PER_MINUTE` | `5` | AI requests per minute |
| `RATE_LIMIT_PER_DAY` | `50` | AI requests per day |
