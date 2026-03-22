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

Anyone can visit the live URL, select their industry, explore real incident data, and get AI-powered root cause analysis and recommended actions in under 3 seconds — with zero setup.

---

## Live Demo

🌐 **Frontend:** https://ops-intelligence-platform.vercel.app
🔌 **Backend API:** https://ops-intelligence-platform.onrender.com/docs
📁 **GitHub:** https://github.com/kushaljaink/ops-intelligence-platform

> ⚠️ Backend runs on Render's free tier — spins down after 15 min of inactivity. First request may take 30–50 seconds. Visit `/health` first to wake it up.

---

## What Companies Did Before This

| Tier | Tool | Problem |
|---|---|---|
| Tier 1 | Basic dashboards | Numbers on a screen. React after damage is done. |
| Tier 2 | Alert systems | Threshold breached → email. Still reactive. No context, no root cause. |
| Tier 3 | BI Tools (Tableau, PowerBI) | Beautiful historical reports. Tell you what happened, not what's about to happen. |
| Tier 4 | Enterprise platforms (ServiceNow) | $50k–$500k/year, months of integration, built for IT. No predictive AI layer. |

**This platform is different.** It reasons about your data, predicts cascades before they happen, simulates the impact of changes, and deploys an AI agent that investigates autonomously — then waits for your approval before acting.

---

## How It's Different From Claude / ChatGPT

Claude and ChatGPT are general-purpose AI assistants. This platform is a **domain-specific AI system** built on top of an LLM.

| | Claude / ChatGPT | This Platform |
|---|---|---|
| What it knows | Everything generally | Your specific operational data |
| How triggered | You ask it | Monitors and acts autonomously |
| Memory | Per conversation | 30 days persistent in database |
| Output | Generic text answers | Specific numbers, predictions, SOPs |
| Integration | Standalone chat | Live data, webhooks, file upload |
| Role of AI | The product | The reasoning engine inside a larger system |

> This platform uses Groq (same class of technology as Claude) not as the product, but as the **reasoning engine** inside a larger system with its own data layer, business logic, pattern detection, prediction algorithms, and human-in-the-loop control flow.

---

## Supported Industries

8 industries supported out of the box, each with calibrated thresholds, 30 days of seeded historical data with realistic patterns, and industry-appropriate AI analysis:

| Industry | Key Stages | Critical Thresholds |
|---|---|---|
| Cruise Terminal | Baggage Drop → Security → Biometrics | Queue > 50, Processing > 300s |
| Healthcare | Triage → Bed Allocation → Diagnostics | Queue > 20, Processing > 120s |
| Banking & Finance | Loan Verification → KYC → Approval | Queue > 100, Processing > 600s |
| E-commerce & Logistics | Warehouse → Dispatch → Returns | Queue > 200, Processing > 180s |
| Airport Operations | Check-in → Security → Boarding | Queue > 80, Processing > 240s |
| Construction Management | Material Delivery → Framing → Inspection | Queue > 5, Processing > 240s |
| Civil Engineering | Earthworks → Quality Check → Drainage | Queue > 8, Processing > 480s |
| Architecture & Design | Design Review → Permit → Revision | Queue > 10, Processing > 720s |
| Custom | Any workflow you define | User-configurable |

Each industry has **seeded behavioral patterns** — Monday morning material delivery spikes for construction, Thursday/Friday cascade failures for cruise terminals, Monday/Friday deadline rushes for architecture firms.

---

## Intelligence Engine — 5 Phases

### Phase 1 — Data Foundation
30 days of realistic historical metrics seeded per industry. Readings every 2 hours. Built-in patterns: time-of-day peaks, day-of-week failures, cascade relationships between stages. Powers all intelligence features.

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
- **Outcome Tracking** — after resolving an incident, logs what action was taken, categorizes it (staffing/equipment/process/escalation), and records health score before and after
- **Resolution Effectiveness** — tracks per-stage resolution rates, recurrence gaps, and avg resolution time; flags stages where fixes aren't holding
- **Playbook Generator** — generates full SOPs (trigger conditions, immediate actions, escalation, root cause checklist, prevention) grounded in actual past incident data

### Phase 5 — Human-in-the-Loop AI Agent
An autonomous agent built on Groq's native tool-calling API. Investigates the operation using 5 tools, then surfaces every consequential decision to the user before acting. **The agent never acts without user approval.**

**Agent tools:**
- `check_health_scores` — gets current 0–100 score per stage
- `get_open_incidents` — fetches all active incidents with IDs
- `get_cascade_predictions` — checks for active cascade risks
- `get_eta_to_breach` — calculates urgency of declining stages
- `get_recurring_patterns` — pulls 30-day pattern data for a specific stage

**Human-in-the-loop decisions after every investigation:**
- Acknowledge critical issues → user approves or skips
- Generate playbooks for recurring stages → user approves or skips
- Send cascade alert → user approves or skips
- Log investigation to audit trail → user approves or skips

---

## Additional Features

- **File Upload with AI Column Mapping** — upload any CSV or Excel file; Groq automatically identifies which columns map to stage/queue/processing/throughput, regardless of column names
- **Community Suggestions** — built-in feedback system; anyone can submit improvement ideas directly from the dashboard
- **Webhook Ingestion** — `POST /webhook/events` accepts live operational data from external systems; auto-creates incidents and triggers AI analysis for HIGH severity events
- **Email Alerts** — HIGH severity incidents and new suggestions trigger email notifications via Resend
- **Audit Trail** — every AI analysis, agent investigation, and outcome is logged with timestamps

---

## Tech Stack

| Layer | Technology | Notes |
|---|---|---|
| Frontend | Next.js 16 + TypeScript + Tailwind | Deployed on Vercel, auto-deploys on push |
| Backend API | FastAPI (Python) | Deployed on Render free tier |
| Database | Supabase (PostgreSQL) | 6 tables: incidents, workflow_metrics, analysis_logs, incident_outcomes, recommendations, suggestions |
| AI — Production | Groq (llama-3.3-70b-versatile) | Free tier, 2–3 second response times |
| AI — Local Dev | Ollama + llama3.2 | Still works locally for development |
| Agent | Groq native tool-calling | No LangChain — direct function calling via OpenAI-compatible API |
| File Parsing | openpyxl + python-multipart | Excel and CSV upload support |
| Email | Resend | Alerts for HIGH severity incidents and suggestions |
| Frontend Hosting | Vercel | Always on, auto-deploy |
| Backend Hosting | Render | Free tier, spins down after 15 min |
| Version Control | GitHub | Public repo |

---

## API Reference

### Core
| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Health check |
| GET | `/incidents?industry=cruise` | Get incidents filtered by industry |
| GET | `/incidents/stats?industry=cruise` | Stats with trend vs yesterday |
| PATCH | `/incidents/{id}/resolve` | Mark incident resolved |
| POST | `/analyze-incident/{id}` | AI analysis with confidence score |
| POST | `/incidents/{id}/outcome` | Log what action was taken post-resolution |
| GET | `/incidents/{id}/analysis-history` | Full AI analysis history for an incident |

### Intelligence Engine
| Method | Endpoint | Description |
|---|---|---|
| GET | `/intelligence/health-scores?industry=cruise` | Stage health scores + trend |
| GET | `/intelligence/recurring-patterns?industry=cruise` | 30-day breach pattern analysis |
| GET | `/intelligence/cascade-predictions?industry=cruise` | Active cascade risks with confidence % |
| GET | `/intelligence/anomaly-scores?industry=cruise` | Anomaly vs 30-day baseline |
| GET | `/intelligence/eta-to-breach?industry=cruise` | Hours to critical threshold via linear regression |
| GET | `/intelligence/capacity-forecast?industry=cruise` | 7-day risk forecast from historical patterns |
| GET | `/intelligence/whatif-simulation?stage=security_check&change=add_staff&magnitude=2` | Simulate operational changes |
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
| POST | `/webhook/events` | Ingest live operational data from external systems |
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
incidents           -- Active incidents per industry and stage
workflow_metrics    -- Raw time-series metrics (health score, queue, processing, throughput)
analysis_logs       -- AI analysis history with confidence scores, triggered_by
incident_outcomes   -- Logged resolution actions and health before/after
recommendations     -- Static recommendations per incident
suggestions         -- Community improvement suggestions
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
# source venv/bin/activate     # Mac/Linux
pip install -r requirements.txt

# Create .env with:
# SUPABASE_URL=your_url
# SUPABASE_KEY=your_service_role_key (legacy eyJ format)
# GROQ_API_KEY=your_groq_key

uvicorn main:app --reload      # Runs on localhost:8000

# Frontend (new terminal)
cd frontend
npm install
npm run dev                    # Runs on localhost:3000
```

---

## Maintenance (Free Tier)

**Weekly (2 minutes):**
- Visit Supabase dashboard to keep project active (pauses after 7 days of inactivity)
- Visit `https://ops-intelligence-platform.onrender.com/health` to wake Render backend

**Before sharing with a recruiter:**
1. Visit `/health` — wait for `{"status":"ok"}`
2. Open the live Vercel URL — confirm incidents load for your selected industry
3. Click **Analyze with AI** on one incident — confirm Groq responds in ~3 seconds
4. Run **AI Agent Investigation** — confirm 5 tool calls complete and decision points appear
5. Share the links

---

## Contributing

Have an idea to improve this platform? Two ways:

1. **From the live site** — click any industry's dashboard, scroll to the **Intelligence Engine → Community** tab, and submit a suggestion directly. It shows up live for everyone.

2. **Via GitHub** — open an issue at [github.com/kushaljaink/ops-intelligence-platform/issues](https://github.com/kushaljaink/ops-intelligence-platform/issues) with your feature request, bug report, or industry suggestion.

Want to add a new industry? The pattern is:
- Add thresholds to `INDUSTRY_THRESHOLDS` in `main.py` and `ops_agent.py`
- Add industry context to `INDUSTRY_CONTEXT` in `page.tsx`
- Add to `INDUSTRIES` array in `page.tsx`
- Seed demo incidents and 30 days of metrics via SQL

---

## Built By

**Kushal Jain** — March 2026

Built end-to-end using VS Code + Claude Code + Claude.ai.

🌐 Live: https://ops-intelligence-platform.vercel.app
📁 GitHub: https://github.com/kushaljaink/ops-intelligence-platform
🔌 API: https://ops-intelligence-platform.onrender.com/docs
