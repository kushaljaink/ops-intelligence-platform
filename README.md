# Ops Intelligence Platform

**AI-powered workflow monitoring, bottleneck detection, and operational intelligence — across any industry.**

[![Live Demo](https://img.shields.io/badge/Live%20Demo-ops--intelligence--platform.vercel.app-6366f1?style=for-the-badge)](https://ops-intelligence-platform.vercel.app)
[![API Docs](https://img.shields.io/badge/API%20Docs-Render-22c55e?style=for-the-badge)](https://ops-intelligence-platform.onrender.com/docs)
[![GitHub](https://img.shields.io/badge/GitHub-kushaljaink-181717?style=for-the-badge&logo=github)](https://github.com/kushaljaink/ops-intelligence-platform)
[![Built With](https://img.shields.io/badge/Built%20With-Groq%20%7C%20FastAPI%20%7C%20Next.js-orange?style=for-the-badge)]()

---

## What It Does

Organizations run critical workflows across many systems, teams, and handoffs. When those workflows break, the consequences are real — delays, revenue loss, customer impact, and teams firefighting instead of working proactively.

**Ops Intelligence Platform detects workflow bottlenecks before they become crises.**

Anyone can visit the live URL, sign up for free, connect their real operational data via webhook, and get AI-powered root cause analysis, cascade predictions, breach forecasts, and autonomous agent investigations — all with human approval at every consequential step.

---

## Live Demo

🌐 **Frontend:** https://ops-intelligence-platform.vercel.app
🔧 **Backend API:** https://ops-intelligence-platform.onrender.com/docs
💻 **GitHub:** https://github.com/kushaljaink/ops-intelligence-platform

> ⚠️ Backend runs on Render's free tier — spins down after 15 min of inactivity. First request may take 30–50 seconds. Visit `/health` to wake it up before a demo.

---

## What Companies Did Before This

| Tier | Tool | Problem |
|---|---|---|
| Tier 1 | Basic dashboards | Numbers on a screen. React after damage is done. |
| Tier 2 | Alert systems | Threshold breached → email. Still reactive. No context, no root cause. |
| Tier 3 | BI Tools (Tableau, PowerBI) | Beautiful historical reports. Tell you what happened, not what's about to happen. |
| Tier 4 | Enterprise platforms (ServiceNow) | $50k–$500k/year, months of integration, built for IT. No predictive AI layer. |

**This platform is different.** It reasons about your data, predicts cascades before they happen, simulates the impact of operational changes, correlates alerts to cut noise, and runs an autonomous AI agent that investigates — then waits for your approval before acting.

---

## How It's Different From Claude / ChatGPT

| | Claude / ChatGPT | This Platform |
|---|---|---|
| What it knows | Everything generally | Your specific operational data |
| How triggered | You ask it | Monitors and acts autonomously |
| Memory | Per conversation | 30 days persistent in database |
| Output | Generic text answers | Specific numbers, predictions, SOPs |
| Integration | Standalone chat | Live data via webhooks, file upload, API |
| Role of AI | The product | The reasoning engine inside a larger system |

---

## Supported Industries

8 industries with calibrated thresholds, 30 days of seeded historical data with realistic patterns, and industry-appropriate AI analysis:

| Industry | Key Stages | Critical Thresholds |
|---|---|---|
| Cruise Terminal | Baggage Drop → Security → Biometrics | Queue > 50, Processing > 300s |
| Healthcare | ED Triage → Bed Allocation → Diagnostics | Queue > 20, Processing > 120s |
| Banking & Finance | Loan Verification → KYC → Approval | Queue > 100, Processing > 600s |
| E-commerce & Logistics | Warehouse → Dispatch → Returns | Queue > 200, Processing > 180s |
| Airport Operations | Check-in → Security → Boarding | Queue > 80, Processing > 240s |
| Construction Management | Material Delivery → Framing → Inspection | Queue > 5, Processing > 240s |
| Civil Engineering | Earthworks → Quality Check → Drainage | Queue > 8, Processing > 480s |
| Architecture & Design | Design Review → Permit → Revision | Queue > 10, Processing > 720s |
| Custom | Any workflow you define | User-configurable |

---

## Intelligence Engine — 5 Phases

### Phase 1 — Data Foundation
30 days of realistic historical metrics per industry with seeded behavioral patterns: Monday morning material delivery spikes for construction, Thursday/Friday cascade failures for cruise terminals, Monday/Friday deadline rushes for architecture. Powers all downstream intelligence.

### Phase 2 — Pattern Intelligence
- **Stage Health Scores** — 0–100 score per stage based on last 24hrs of metrics with improving/degrading/stable trend indicators
- **Recurring Pattern Detection** — identifies stages that fail repeatedly, pinpoints peak failure hours and days from 30 days of data
- **Cascade Prediction** — detects when Stage A failing causes Stage B to degrade 2hrs later; shows confidence % and fires live alerts when source stage is currently stressed
- **Anomaly Scoring** — flags stages running below their 30-day baseline before they hit threshold

### Phase 3 — Predictive Intelligence
- **ETA to Breach** — linear regression on health score trajectory; projects hours until each stage hits critical threshold (40/100)
- **7-Day Capacity Forecast** — maps 30-day historical breach patterns to the next 7 days; warns about high-risk time windows before they happen
- **What-If Simulation** — simulates operational changes (add staff, reduce queue, upgrade equipment, extend hours) and shows projected before/after metrics with AI assessment

### Phase 4 — Recommendation Intelligence
- **Confidence Scoring** — every AI analysis shows a 0–100% confidence score extracted from Groq's language, with a visual confidence bar
- **Grounded Analysis** — AI is given actual metric values (queue=67, processing=420s, health trajectory 81→74→65) before analyzing — no generic advice
- **Outcome Tracking** — after resolving an incident, logs what action was taken, categorizes it (staffing/equipment/process/escalation), and records health before and after
- **Resolution Effectiveness** — tracks per-stage resolution rates, recurrence gaps, and avg resolution time; flags stages where fixes aren't holding
- **Playbook Generator** — generates full SOPs (trigger conditions, immediate actions, escalation, root cause checklist, prevention) grounded in actual past incident data

### Phase 5 — Human-in-the-Loop AI Agent
An autonomous agent built on Groq's native tool-calling API. Investigates the operation using 5 tools, then surfaces every consequential decision to the user before acting. **The agent never acts without user approval.**

**Agent tools:**
- `check_health_scores` — current 0–100 score per stage
- `get_open_incidents` — all active incidents with IDs and severity
- `get_cascade_predictions` — active cascade risks with confidence %
- `get_eta_to_breach` — urgency of declining stages via linear regression
- `get_recurring_patterns` — 30-day pattern data for a specific stage

---

## Additional Features

### Authentication & User Data Isolation
- Email/password signup via Supabase Auth
- Unauthenticated visitors see demo data only
- Signed-in users see demo data + their own private operational data
- Personal API keys generated on signup for webhook authentication

### Connect Your System (Webhook)
- `POST /webhook/events` accepts live operational data from any system
- Curl, Python, and JavaScript code snippets available in the dashboard
- **Alert correlation** — duplicate incidents on the same stage within 30 minutes are merged instead of creating noise
- **Test button** — send a sample event and watch it appear as a live incident

### File Upload with AI Column Mapping
- Upload any Excel or CSV file — Groq automatically maps your columns to stage/queue/processing/throughput
- No specific format required — works with whatever column names you already use

### Slack Alerts
- HIGH severity incidents and new community suggestions trigger Slack notifications
- Configurable via `SLACK_WEBHOOK_URL` environment variable

### Community Suggestions
- Built-in feedback form on the dashboard
- All suggestions visible to everyone in real time
- New suggestions trigger email notification to the platform owner

### Email Alerts
- HIGH severity incidents trigger email via Resend
- Community suggestions trigger notification emails

### Audit Trail
- Every AI analysis, agent investigation, and resolution outcome logged with timestamps

---

## Tech Stack

| Layer | Technology | Notes |
|---|---|---|
| Frontend | Next.js 16 + TypeScript + Tailwind | Deployed on Vercel, auto-deploys on push |
| Backend API | FastAPI (Python) | Deployed on Render free tier |
| Database | Supabase (PostgreSQL) | 7 tables with RLS, user isolation |
| Auth | Supabase Auth | Email/password, JWT, personal API keys |
| AI — Production | Groq (llama-3.3-70b-versatile) | Free tier, 2–3 second response times |
| AI — Local Dev | Ollama + llama3.2 | Still works locally for development |
| Agent | Groq native tool-calling | No LangChain — direct function calling |
| File Parsing | openpyxl + python-multipart | Excel and CSV upload support |
| Email | Resend | Alerts for HIGH severity incidents |
| Slack | Incoming Webhooks | Real-time ops alerts |
| Frontend Hosting | Vercel | Always on, auto-deploy |
| Backend Hosting | Render | Free tier, spins down after 15 min |

---

## API Reference

### Core
| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Health check |
| GET | `/auth/me` | Get authenticated user info and API key |
| GET | `/incidents?industry=cruise` | Get incidents (demo + user's own if authenticated) |
| GET | `/incidents/stats?industry=cruise` | Stats with trend vs yesterday |
| PATCH | `/incidents/{id}/resolve` | Mark incident resolved |
| POST | `/analyze-incident/{id}` | AI analysis grounded in actual metrics |
| POST | `/incidents/{id}/outcome` | Log resolution action and outcome |
| GET | `/incidents/{id}/analysis-history` | Full AI analysis history |

### Intelligence Engine
| Method | Endpoint | Description |
|---|---|---|
| GET | `/intelligence/health-scores?industry=cruise` | Stage health scores + trend |
| GET | `/intelligence/recurring-patterns?industry=cruise` | 30-day breach pattern analysis |
| GET | `/intelligence/cascade-predictions?industry=cruise` | Active cascade risks with confidence % |
| GET | `/intelligence/anomaly-scores?industry=cruise` | Anomaly vs 30-day baseline |
| GET | `/intelligence/eta-to-breach?industry=cruise` | Hours to critical threshold |
| GET | `/intelligence/capacity-forecast?industry=cruise` | 7-day risk forecast |
| GET | `/intelligence/whatif-simulation` | Simulate operational changes |
| GET | `/intelligence/resolution-effectiveness?industry=cruise` | Per-stage resolution analytics |
| GET | `/intelligence/playbook/{stage}?industry=cruise` | Generate AI-powered SOP |

### AI Agent
| Method | Endpoint | Description |
|---|---|---|
| POST | `/agent/investigate` | Run autonomous AI agent investigation |
| POST | `/agent/decision` | Submit human decision on agent finding |

### Data Ingestion
| Method | Endpoint | Description |
|---|---|---|
| POST | `/webhook/events` | Ingest live operational data (supports `api_key` for user isolation) |
| POST | `/test-webhook?industry=healthcare` | Send a test event |
| GET | `/connect-info` | Get webhook URL and code snippets |
| POST | `/analyze-custom` | Analyze custom workflow data (form/CSV) |
| POST | `/extract-and-analyze` | Upload any file — AI maps columns automatically |

### Community
| Method | Endpoint | Description |
|---|---|---|
| POST | `/suggestions` | Submit an improvement suggestion |
| GET | `/suggestions` | Get all community suggestions |

---

## Database Schema

```sql
incidents           -- Active incidents per industry and stage, user_id for isolation
workflow_metrics    -- Raw time-series metrics, user_id for isolation
analysis_logs       -- AI analysis history with confidence scores
incident_outcomes   -- Logged resolution actions and health before/after
recommendations     -- Static recommendations per incident
suggestions         -- Community improvement suggestions
user_api_keys       -- Personal API keys for webhook authentication
```

---

## Local Development

**Prerequisites:** Python 3.11+, Node.js 20+, Supabase account, Groq API key (free at console.groq.com)

```bash
# Clone
git clone https://github.com/kushaljaink/ops-intelligence-platform
cd ops-intelligence-platform

# Backend
cd backend
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt

# backend/.env
SUPABASE_URL=your_project_url
SUPABASE_KEY=your_service_role_key
GROQ_API_KEY=your_groq_key
SUPABASE_JWT_SECRET=your_jwt_secret
SLACK_WEBHOOK_URL=optional

uvicorn main:app --reload      # http://localhost:8000

# Frontend (new terminal)
cd frontend
npm install

# frontend/.env.local
NEXT_PUBLIC_SUPABASE_URL=your_project_url
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_anon_key

npm run dev                    # http://localhost:3000
```

---

## Connecting Real Data

Once signed in, get your personal API key from the **Connect** panel. Then POST your operational metrics:

```python
import httpx

httpx.post("https://ops-intelligence-platform.onrender.com/webhook/events", json={
    "api_key": "your_personal_api_key",
    "events": [{
        "stage": "ed_triage",
        "queue_size": 32,
        "processing_time_seconds": 210,
        "throughput": 7,
        "industry": "healthcare"
    }]
})
```

Your data appears privately on your dashboard. The platform automatically detects threshold breaches, correlates related alerts, calculates health scores, and makes the incident available for AI analysis and agent investigation.

---

## Maintenance (Free Tier)

**Weekly:** Visit Supabase dashboard to keep project active (pauses after 7 days). Visit `/health` to wake Render.

**Before a demo:**
1. Visit `/health` — wait for `{"status":"ok"}`
2. Refresh the dashboard — confirm incidents load
3. Click **Analyze with AI** on one incident — confirm Groq responds in ~3 seconds
4. Run **AI Agent Investigation** — confirm 5 tool calls complete
5. Share the link

---

## Contributing

**From the live site** — go to the **Community** tab in the Intelligence Engine and submit a suggestion. Shows up live for everyone.

**Via GitHub** — open an issue at [github.com/kushaljaink/ops-intelligence-platform/issues](https://github.com/kushaljaink/ops-intelligence-platform/issues).

**Adding a new industry:**
1. Add thresholds to `INDUSTRY_THRESHOLDS` in `main.py` and `ops_agent.py`
2. Add context to `INDUSTRY_CONTEXT` in `page.tsx`
3. Add to `INDUSTRIES` array in `page.tsx`
4. Seed demo incidents and 30 days of metrics via SQL

---

## Built By

**Kushal Jain** — March 2026

Built end-to-end using VS Code + Claude Code + Claude.ai.

🌐 https://ops-intelligence-platform.vercel.app
💻 https://github.com/kushaljaink/ops-intelligence-platform
🔧 https://ops-intelligence-platform.onrender.com/docs
