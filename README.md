# Ops Intelligence Platform

AI-powered early warning and decision support system for operations teams.

[![Live Demo](https://img.shields.io/badge/Live%20Demo-Vercel-black?style=for-the-badge&logo=vercel)](https://ops-intelligence-platform.vercel.app)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-000000?style=for-the-badge&logo=nextdotjs&logoColor=white)](https://nextjs.org)
[![Supabase](https://img.shields.io/badge/Supabase-3ECF8E?style=for-the-badge&logo=supabase&logoColor=white)](https://supabase.com)
[![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)

---

| | |
|---|---|
| **Live App** | [https://ops-intelligence-platform.vercel.app](https://ops-intelligence-platform.vercel.app) |
| **API Docs** | [https://ops-intelligence-platform.onrender.com/docs](https://ops-intelligence-platform.onrender.com/docs) |
| **GitHub** | [https://github.com/kushaljaink/ops-intelligence-platform](https://github.com/kushaljaink/ops-intelligence-platform) |

---

## The Problem

Large-scale operations — cruise embarkation, airport security, healthcare admissions, warehouse fulfilment, bank branch workflows — run across many interconnected systems. Thousands of people move through these systems every day, and keeping them moving smoothly depends on dozens of processes working in sync.

When something breaks, it rarely announces itself. A queue backs up. A processing step slows down. Throughput drops. By the time anyone notices, there is already a delay. And with delay comes customer impact, revenue loss, and employees scrambling to fix something that could have been caught ten minutes earlier.

The core challenge is not that teams lack data. Most operations are surrounded by data. The challenge is that no single system connects the dots fast enough to matter. Dashboards show what has already happened. Alerts fire after thresholds are already crossed. Teams work in separate tools — one for monitoring, one for ticketing, one for communication — and spend more time coordinating than fixing.

The result: operations teams are permanently reactive. They fight fires instead of preventing them.

---

## How companies handle it today

Most operations platforms fall into one of four categories:

- **Workflow tools** (ServiceNow, Jira, Monday) — track tasks and tickets after a problem is reported
- **Dashboards** (Grafana, Datadog, Tableau) — visualise what is happening right now, but require a human to interpret it
- **Alerting systems** (PagerDuty, OpsGenie) — notify teams when a pre-defined threshold is crossed, but only after the fact
- **AI copilots** (ChatGPT, Copilot integrations) — answer questions when asked, but don't watch your systems or act proactively

Each of these is useful. None of them does the full job.

What they do not do is automatically detect that something is going wrong across multiple steps of a workflow, explain why it is likely happening, and tell the team what to do about it — all before the problem reaches the customer.

That gap is where this project sits.

---

## The Solution

**Ops Intelligence Platform** is an early warning and decision support system for operations teams. It watches workflow signals, detects anomalies, creates incident records, and gives teams an AI-generated diagnosis and recommended action — without anyone having to ask.

The demo use case is **CruiseOps AI**: a simulated cruise terminal where passengers move through a pipeline of stages — baggage drop, security screening, biometric check-in, and boarding. Each stage can develop bottlenecks, failures, or delays. The platform monitors the entire pipeline and surfaces problems the moment they emerge.

This is not a chatbot. It is not just a dashboard. It is not just an alert.

It does four things together:

1. **Detection** — identifies when a workflow stage is behaving abnormally
2. **Diagnosis** — explains the likely cause using an AI model with full incident context
3. **Recommendation** — suggests concrete next actions for the operations team
4. **Follow-up** — records the incident and any workflow events for audit and learning

---

## How it works

The platform is built around a simple but powerful loop:

**1. Signals are monitored**
Workflow metrics — queue sizes, processing times, throughput rates — are tracked across each stage of the operation. In the demo, this covers the full cruise embarkation pipeline from arrival to boarding.

**2. A rules engine detects bottlenecks**
When a metric crosses a defined threshold, the system creates an incident record automatically. No human needs to spot it first. Each incident captures the affected stage, severity level, current status, and a plain-language description of what was detected.

**3. AI diagnoses the incident**
When an operator clicks "Analyze with AI", the incident details are sent to a locally-hosted LLM (llama3.2 via Ollama). The model reads the full incident context — stage, severity, description, service — and returns a structured analysis: what likely caused this, and what the team should do next.

**4. The dashboard surfaces everything in one place**
Active incidents are shown with severity badges, status, detection time, and one-click AI analysis. There is no need to jump between tools. The on-call engineer sees the problem, the context, and the recommended action on a single screen.

---

## Why this is different

Here is the typical operations workflow today:

> Monitor dashboards → someone spots something wrong → investigate across multiple tools → message the right team → wait for them to assess → decide what to do

Every step in that chain takes time. Each handoff introduces delay. By the time the team is aligned on what to do, the problem has already cascaded.

Here is how this platform changes that:

> System detects abnormal behavior → incident record created automatically → AI pulls together the context → diagnosis and recommended action delivered in seconds → team acts immediately

The difference is not just speed. It is the removal of the ambiguous middle steps where things fall through the cracks: the analyst who did not notice the graph drift, the alert that went to the wrong channel, the on-call engineer who spent twenty minutes investigating before finding the right data.

This platform reduces time-to-notice, time-to-triage, and time-to-coordinate — the three biggest contributors to operational downtime.

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

## Note on free tier hosting

This project runs entirely on free-tier infrastructure — here is what to expect:

- **Vercel (frontend)** — Always on. Loads instantly.
- **Render (backend)** — Spins down after inactivity. The first request after a cold start takes **30–50 seconds** to respond; subsequent requests are fast.
- **Supabase (database)** — Stays active as long as the project is accessed occasionally. No cold start.

> **Tip for reviewers:** Before sharing or demoing, visit [https://ops-intelligence-platform.onrender.com/health](https://ops-intelligence-platform.onrender.com/health) to wake the backend up. Once it returns `{"status":"ok"}`, the app is fully live.

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
git clone https://github.com/kushaljaink/ops-intelligence-platform.git
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

## Resume bullet points

- Built a full-stack AI operations platform using **FastAPI**, **Next.js**, and **Supabase**, deployed on **Vercel** and **Render**
- Integrated **Ollama (llama3.2)** to generate real-time root cause analysis and remediation recommendations for production incidents
- Designed a **pgvector**-backed Supabase schema for incident storage and semantic search across operational events
- Implemented a responsive dark-theme dashboard surfacing live incident severity, status, and AI analysis with zero page reloads

---

## Maintenance Notes

### Weekly checklist (2 minutes)
- Visit [supabase.com](https://supabase.com) and open the project dashboard to keep the free tier active (pauses after 7 days of inactivity)
- Visit [https://ops-intelligence-platform.onrender.com/health](https://ops-intelligence-platform.onrender.com/health) to wake up the backend

### Before sharing with a recruiter (30 seconds)
1. Visit [https://ops-intelligence-platform.onrender.com/health](https://ops-intelligence-platform.onrender.com/health) and wait for `{"status":"ok"}`
2. Visit [https://ops-intelligence-platform.vercel.app](https://ops-intelligence-platform.vercel.app) and confirm incidents load
3. Then share the links

### What stays on automatically
- **Vercel frontend** — always on, no action needed
- **Supabase database** — stays active with weekly login
- **Render backend** — spins down after 15 min inactivity, wakes up on first request (30–50 sec delay)
