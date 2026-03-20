# Ops Intelligence Platform

AI-powered incident monitoring and diagnosis platform for operations teams.

**Live demo:** [https://ops-intelligence-platform.vercel.app](https://ops-intelligence-platform.vercel.app)

---

## What it does

Ops Intelligence Platform gives operations teams an edge by turning raw incident data into actionable intelligence — fast.

- **Early warning** — Continuously surfaces open and high-severity incidents from your data pipeline so on-call engineers see what matters immediately, without digging through logs.
- **Instant diagnosis** — Each incident card shows severity, status, affected service, and a human-readable description so teams can triage at a glance.
- **AI-powered recommendations** — A single click runs the incident through a locally-hosted LLM (llama3.2 via Ollama) that returns a root cause analysis and concrete remediation steps in seconds, directly on the incident card.

Built for teams that need fast answers during an outage, not a ticket queue.

---

## Tech stack

| Layer | Technology |
|---|---|
| Backend API | FastAPI (Python) |
| Frontend | Next.js 14 (App Router, TypeScript) |
| Database | Supabase (PostgreSQL) |
| Vector search | pgvector |
| AI inference | Ollama · llama3.2 |
| Frontend hosting | Vercel |
| Backend hosting | Render |

---

## Screenshots

> _Screenshots coming soon._

---

## How to run locally

### Prerequisites

- Python 3.11+
- Node.js 18+
- [Ollama](https://ollama.com) installed and running
- A Supabase project with `incidents`, `recommendations`, and `workflow_events` tables

### 1. Clone the repo

```bash
git clone https://github.com/your-username/ops-intelligence-platform.git
cd ops-intelligence-platform
```

### 2. Backend

```bash
cd backend
pip install -r requirements.txt
```

Create a `.env` file in `backend/`:

```env
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_anon_key
```

Start the API:

```bash
uvicorn main:app --reload
```

The backend will be available at `http://localhost:8000`.

### 3. Pull the AI model

```bash
ollama pull llama3.2
```

Make sure Ollama is running (`ollama serve`) before using the Analyze feature.

### 4. Frontend

```bash
cd frontend
npm install
npm run dev
```

The app will be available at `http://localhost:3000`.

> **Note:** By default the frontend points to the production backend on Render. To use your local backend, update the fetch URLs in `frontend/app/page.tsx` to `http://localhost:8000`.

---
