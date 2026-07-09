# Saral — Making Learning Simpler

> **IBM SkillsBuild × Edunet Foundation Internship Project**
> Powered by **IBM watsonx.ai** · meta-llama/llama-3-3-70b-instruct

[![IBM watsonx.ai](https://img.shields.io/badge/IBM-watsonx.ai-0f62fe?logo=ibm&logoColor=white)](https://www.ibm.com/watsonx)
[![Python](https://img.shields.io/badge/Python-3.10-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.0.3-000000?logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## What is Saral?

**Saral** (सरल, Hindi for *simple*) is an AI-powered educational assistant that helps students learn more effectively from their own study material.

Students upload a PDF, DOCX, or TXT document. Saral processes it locally using a **Retrieval-Augmented Generation (RAG)** pipeline — embedding the document into a local vector database (ChromaDB) using `sentence-transformers`. When the student asks a question or requests a summary, Saral retrieves the most relevant chunks from the document and uses **IBM watsonx.ai** to generate a grounded, accurate response.

No hallucinations. No irrelevant answers. Everything is anchored to the student's own study material.

---

## IBM Cloud Platform Usage

This project uses the **IBM watsonx.ai** foundation model service:

| Component | IBM Product |
|---|---|
| Language Model | IBM watsonx.ai — `meta-llama/llama-3-3-70b-instruct` |
| API Region | `au-syd` (Sydney) |
| Plan | IBM Lite (Free Tier) |
| Authentication | IBM Cloud IAM API Key |

All AI calls are made **server-side** via the `ibm-watsonx-ai` Python SDK. No API keys are ever exposed to the browser.

---

## Features

| Feature | Description |
|---|---|
| 💬 **Ask Saral** | Conversational Q&A grounded in your uploaded documents via RAG |
| ✨ **Simplify** | Rewrite complex passages at Beginner / Intermediate / Advanced level |
| 📋 **Summary** | Short, Bullet, Detailed, One-minute, or Exam Notes summaries |
| 🎯 **Quiz Generator** | MCQ, True/False, Short or Long-answer questions at 3 difficulty levels |
| 🔍 **Explain Term** | Definition + meaning + example + real-world analogy for any concept |
| 📚 **Revision Mode** | Flashcards, Quick Notes, or Exam Cheat Sheet from your material |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Saral Architecture                        │
│                                                                  │
│  Browser (HTML/CSS/Vanilla JS)                                   │
│       │ fetch()                                                  │
│       ▼                                                          │
│  Flask Backend (Python 3.10)                                     │
│    ├── Upload Route    → file validation → SHA-256 dedup         │
│    ├── Document Route  → PyMuPDF / python-docx / chardet         │
│    ├── Chat Route      → RAG → IBM watsonx.ai → response         │
│    ├── Summary Route   → RAG → IBM watsonx.ai → response         │
│    ├── Quiz Route      → RAG → IBM watsonx.ai → JSON parse       │
│    ├── Simplify Route  → IBM watsonx.ai (direct, no RAG)         │
│    ├── Explain Route   → IBM watsonx.ai (optional RAG context)   │
│    └── Revision Route  → RAG → IBM watsonx.ai → response         │
│                                                                  │
│  Local Storage                     IBM Cloud                     │
│    ├── SQLite (metadata)            └── watsonx.ai               │
│    ├── ChromaDB (vectors)               (LLM inference)          │
│    └── uploads/ (files)                                          │
│                                                                  │
│  Local ML (no IBM quota cost)                                    │
│    └── sentence-transformers / all-MiniLM-L6-v2                 │
└─────────────────────────────────────────────────────────────────┘
```

**RAG Pipeline (per query):**
1. Student question → embedded locally by `sentence-transformers`
2. Cosine similarity search in ChromaDB → top-K most relevant document chunks retrieved
3. Chunks assembled into prompt context
4. IBM watsonx.ai generates a grounded answer from context only
5. Response cached in-memory to minimise IBM Lite quota usage

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.10, Flask 3.0.3 |
| AI | IBM watsonx.ai (`ibm-watsonx-ai` SDK) |
| Embeddings | `sentence-transformers` (all-MiniLM-L6-v2, local) |
| Vector DB | ChromaDB 0.5.5 (persistent, local) |
| Document Parsing | PyMuPDF, python-docx, chardet |
| Database | SQLite (via Python `sqlite3`) |
| Frontend | HTML5, CSS3 (IBM design system), Vanilla JavaScript |
| Rate Limiting | Flask-Limiter |
| CORS | Flask-CORS |

---

## Local Setup

### Prerequisites

- Python 3.10+
- An IBM Cloud account with watsonx.ai access
- A watsonx.ai project

### 1. Clone the repository

```bash
git clone https://github.com/your-username/SaraL.git
cd SaraL
```

### 2. Create a virtual environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

> **Note:** First run will download the `all-MiniLM-L6-v2` embedding model (~90 MB) from HuggingFace. This is a one-time download.

### 4. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and fill in your IBM credentials:

```env
WATSONX_API_KEY=your_ibm_cloud_api_key_here
WATSONX_PROJECT_ID=your_watsonx_project_id_here
WATSONX_URL=https://au-syd.ml.cloud.ibm.com
WATSONX_MODEL_ID=meta-llama/llama-3-3-70b-instruct
FLASK_SECRET_KEY=change-this-to-a-random-secret
FLASK_DEBUG=true
```

**Where to get IBM credentials:**
1. Log in to [IBM Cloud](https://cloud.ibm.com)
2. Go to **Manage → Access (IAM) → API keys** → Create an API key
3. Go to [watsonx.ai](https://dataplatform.cloud.ibm.com/wx/home) → Create a project → Copy the Project ID from the project settings

### 5. Run the application

```bash
python app.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000) in your browser.

---

## Usage

1. **Upload** — Go to the Dashboard and upload a PDF, DOCX, or TXT study file. Saral validates, indexes, and stores it locally.
2. **Select** — Click **Use** on any indexed document to set it as the active document.
3. **Ask** — Navigate to **Ask Saral** and ask questions about your document.
4. **Explore** — Use Summary, Quiz, Simplify, Explain, or Revision features from the sidebar.

---

## Project Structure

```
SaraL/
├── app.py                         # Entry point
├── backend/
│   ├── app.py                     # Flask app factory
│   ├── config.py                  # Centralised configuration
│   ├── database.py                # SQLite schema + migrations
│   ├── extensions.py              # Flask-Limiter, Flask-CORS
│   ├── routes/
│   │   ├── document_routes.py     # Upload, list, delete, status
│   │   ├── chat_routes.py         # Ask Saral (RAG + LLM)
│   │   ├── summary_routes.py      # Summary generation
│   │   ├── quiz_routes.py         # Quiz generation
│   │   ├── simplify_routes.py     # Text simplification
│   │   ├── explain_routes.py      # Term explanation
│   │   ├── revision_routes.py     # Flashcards, notes, cheat sheet
│   │   └── settings_routes.py     # App settings + cache
│   ├── services/
│   │   ├── llm_service.py         # IBM watsonx.ai wrapper
│   │   ├── rag_service.py         # RAG retrieval pipeline
│   │   ├── document_service.py    # Ingestion pipeline (async)
│   │   ├── embedding_service.py   # Local sentence-transformers
│   │   └── cache_service.py       # In-memory response cache
│   └── utils/
│       ├── text_utils.py          # PDF/DOCX/TXT extraction + chunking
│       ├── prompt_utils.py        # All LLM prompt templates
│       ├── file_utils.py          # File validation + hashing
│       └── logger.py              # Structured logging
├── frontend/
│   ├── templates/                 # Jinja2 HTML templates
│   └── static/
│       ├── css/                   # IBM design system CSS
│       └── js/                    # Vanilla JS modules
├── instance/                      # SQLite database (auto-created)
├── uploads/                       # Uploaded files (auto-created)
├── vectordb/                      # ChromaDB data (auto-created)
├── .env.example                   # Environment variable template
├── requirements.txt               # Python dependencies
├── DEPLOYMENT.md                  # Deployment guide (Render + IBM Cloud)
└── LICENSE                        # MIT License
```

---

## IBM watsonx.ai Lite Plan Optimisations

This project is built to operate efficiently within the **IBM Lite (free) quota**:

- ✅ **Response caching** — identical questions return cached results without an IBM API call
- ✅ **Rate limiting** — 5 requests/minute, 50 requests/day (configurable)
- ✅ **Local embeddings** — document indexing uses `sentence-transformers`, not IBM API
- ✅ **RAG context limiting** — only top-K relevant chunks are sent (not full documents)
- ✅ **Token optimisation** — `max_new_tokens` is tuned per feature (not set to maximum)
- ✅ **Server-side only** — no API calls from the browser; all LLM calls go through Flask

---

## Contribution to Society

Saral addresses a real educational gap:

- 🎓 **Accessibility** — Students who struggle with complex textbooks can now access simplified explanations instantly
- 📚 **Self-directed learning** — Students control the pace and depth of their learning
- 🌍 **Language barrier reduction** — Simplify feature makes English academic content accessible to learners at different proficiency levels
- 💰 **Cost-free** — No subscription or per-use fee for the student. The free IBM Lite plan makes this viable for personal use.
- 🔒 **Privacy** — Documents are stored locally. Nothing is uploaded to third-party cloud storage.

---

## Future Scope

| Feature | Description |
|---|---|
| 🌐 Multi-language support | Translate and explain content in regional languages using IBM's multilingual models |
| 🎙️ Voice input | Ask questions via microphone using Web Speech API |
| 👥 Classroom mode | Teacher uploads material; students access it without individual uploads |
| 📊 Learning analytics | Track which concepts students ask about most, identify knowledge gaps |
| 🖼️ Scanned PDF support | OCR integration (Tesseract) for image-based PDFs |
| ☁️ IBM Cloud deployment | Full production deployment on IBM Code Engine with persistent storage |
| 📱 Progressive Web App | Offline-capable PWA for mobile students with limited connectivity |
| 🔗 LMS integration | Moodle/Google Classroom plugin for institutional adoption |

---

## Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for step-by-step instructions to deploy on **Render** (free tier) and **IBM Cloud**.

---

## Internship Attribution

This project was developed as part of the **IBM SkillsBuild × Edunet Foundation AI/ML Internship**.

- **Platform:** IBM watsonx.ai (IBM Cloud, au-syd region)
- **Model:** meta-llama/llama-3-3-70b-instruct
- **Primary Implementation:** IBM Bob (AI-assisted development tool)
- **Developer:** Rohan Das
- **Institution:** [Your Institution Name]

---

## License

[MIT License](LICENSE) © 2026 Rohan Das
