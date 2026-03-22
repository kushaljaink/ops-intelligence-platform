<<<<<<< HEAD
## What This Platform Does
=======

# Ops Intelligence Platform
>>>>>>> d3ab4f3 (Normalize README formatting)

Ops Intelligence Platform simulates a production-style internal operations decision-support system.

<<<<<<< HEAD
It helps teams:
=======
---

## Current Live Data Coverage
>>>>>>> d3ab4f3 (Normalize README formatting)

- detect workflow bottlenecks early
- identify recurring operational risks
- predict SLA breaches before they happen
- simulate intervention strategies
- investigate incidents using AI agents
- generate grounded recommendations
- ingest live public operational signals
- connect internal workflow metrics via webhooks


<<<<<<< HEAD
## Supported Industries

20 operational workflow domains are supported with calibrated thresholds and realistic incident behavior.

| Industry | Mode |
|---|---|
| Healthcare | Hybrid |
| Airport Operations | Hybrid |
| Weather Operations | Hybrid |
| Energy Grid | Hybrid |
| Water Utilities | Hybrid |
| Cruise Terminal | Demo |
| Banking & Finance | Demo |
| E-commerce & Logistics | Demo |
| Construction | Demo |
| Civil Engineering | Demo |
| Architecture | Demo |
| Telecommunications | Demo |
| Manufacturing | Demo |
| Retail | Demo |
| Food Service | Demo |
| Pharmaceutical | Demo |
| Government Services | Demo |
| Real Estate | Demo |
| Education | Demo |
| Media Platforms | Demo |


## Intelligence Engine Architecture

The system runs a multi-layer operational reasoning pipeline.

### Phase 1 — Data Foundation

Supports ingestion from:

- seeded workflow datasets
- uploaded CSV / Excel files
- webhook operational events
- public operational APIs

Live sources automatically degrade to fallback scenarios when unavailable.


### Phase 2 — Pattern Intelligence

Detects:

- weak workflow stages
- recurring bottlenecks
- anomaly signals
- cascade risks

Includes:

- Health Scores
- Recurring Pattern Detection
- Cascade Prediction
- Anomaly Scoring


### Phase 3 — Predictive Intelligence

Forecasts:

- ETA to SLA breach
- queue saturation risk
- throughput collapse risk

Supports intervention simulation:

- increase staffing
- extend processing hours
- adjust queue thresholds


### Phase 4 — Recommendation Intelligence

Each recommendation includes:

- confidence score
- metric grounding
- incident linkage
- historical effectiveness comparison

Outputs remain auditable and explainable.


### Phase 5 — Human-in-the-Loop Investigation Agent

Groq-powered investigation agent analyzes incidents using structured system tools.

Agent tools:

- check_health_scores
- get_open_incidents
- get_cascade_predictions
- get_eta_to_breach
- get_recurring_patterns

The agent proposes actions but never executes changes automatically.


## Authentication & User Isolation

Supabase Auth provides:

- email/password login
- JWT session validation
- per-user dataset isolation
- personal webhook API keys


## Connect Your System (Webhook Ingestion)

Endpoint:

POST `/webhook/events`

Supports ingestion from:

- Python services
- cron jobs
- schedulers
- internal workflow trackers
- monitoring pipelines

Duplicate incident correlation reduces alert noise automatically.


## Free Live Public Connectors

Endpoint:

POST `/fetch-live-data?industry=`

Supported industries:

| Industry | Endpoint Key | Live Support |
|---|---|---|
| Healthcare | healthcare | Yes |
| Airport | airport | Yes |
| Weather | weather | Yes |
| Energy | energy | Optional (API key) |
| Water | water | Optional (API key) |

Response modes returned by the platform:

- Live Data
- Fallback Demo Data
- Demo Data


## File Upload With AI Column Mapping

Upload:

- CSV
- Excel

The platform automatically detects:

- queue size
- processing time
- throughput
- workflow stage names

No template required.


## Audit Trail

Tracks:

- AI investigations
- incident analyses
- recommendations
- resolution outcomes
- decision timestamps


## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js + TypeScript + Tailwind |
| Backend | FastAPI |
| Database | Supabase PostgreSQL |
| Auth | Supabase Auth |
| AI | Groq |
| Agent | Groq tool-calling |
| Parsing | openpyxl + python-multipart |
| Public Data | CMS + FAA + NOAA (+ optional EIA + USGS) |
| Frontend Hosting | Vercel |
| Backend Hosting | Render |
| CI/CD | GitHub → Vercel + Render |


## API Reference

### Core

GET `/health`  
GET `/auth/me`  
GET `/incidents`  
GET `/incidents/stats`  
PATCH `/incidents/{id}/resolve`  
POST `/analyze-incident/{id}`  
POST `/incidents/{id}/outcome`


### Intelligence Engine

GET `/intelligence/health-scores`  
GET `/intelligence/recurring-patterns`  
GET `/intelligence/cascade-predictions`  
GET `/intelligence/anomaly-scores`  
GET `/intelligence/eta-to-breach`  
GET `/intelligence/capacity-forecast`  
GET `/intelligence/whatif-simulation`  
GET `/intelligence/resolution-effectiveness`  
GET `/intelligence/playbook/{stage}`


### AI Agent

POST `/agent/investigate`  
POST `/agent/decision`


### Data Ingestion

POST `/webhook/events`  
POST `/test-webhook`  
GET `/connect-info`  
POST `/analyze-custom`  
POST `/extract-and-analyze`  
POST `/fetch-live-data`
incidents
workflow_metrics
analysis_logs
incident_outcomes
recommendations
suggestions
user_api_keys



## Built By

Kushal Jain

Frontend  
https://ops-intelligence-platform.vercel.app

Backend API  
https://ops-intelligence-platform.onrender.com/docs

GitHub  
https://github.com/kushaljaink/ops-intelligence-platform

## Database Schema
=======
**Hybrid** means the app attempts live refresh first and gracefully falls back to demo-style incidents if the source fails, rate-limits, or is not configured.

---

## What This Platform Does

Ops Intelligence Platform simulates a production-style internal operations decision-support system.

It helps teams:

- detect workflow bottlenecks early
- identify recurring operational risks
- predict SLA breaches before they happen
- simulate intervention strategies
- investigate incidents using AI agents
- generate grounded recommendations
- ingest live public operational signals
- connect internal workflow metrics via webhooks

The system mirrors how real internal tools at companies like Meta, Amazon, and Stripe surface operational intelligence.

---

## Supported Industries

20 operational workflow domains are supported with calibrated thresholds and realistic incident behavior.

Live public ingestion enabled where free sources exist.

| Industry | Mode |
|---|---|
| Healthcare | Hybrid |
| Airport Operations | Hybrid |
| Weather Operations | Hybrid |
| Energy Grid | Hybrid |
| Water Utilities | Hybrid |
| Cruise Terminal | Demo |
| Banking & Finance | Demo |
| E-commerce & Logistics | Demo |
| Construction | Demo |
| Civil Engineering | Demo |
| Architecture | Demo |
| Telecommunications | Demo |
| Manufacturing | Demo |
| Retail | Demo |
| Food Service | Demo |
| Pharmaceutical | Demo |
| Government Services | Demo |
| Real Estate | Demo |
| Education | Demo |
| Media Platforms | Demo |

---

## Intelligence Engine Architecture

The system runs a multi-layer operational reasoning pipeline.

### Phase 1 — Data Foundation

Supports ingestion from:

- seeded workflow datasets
- uploaded CSV / Excel files
- webhook operational events
- public operational APIs

Live sources automatically degrade to fallback scenarios when unavailable.

### Phase 2 — Pattern Intelligence

Detects:

- weak workflow stages
- recurring bottlenecks
- anomaly signals
- cascade risks

Includes:

- Health Scores
- Recurring Pattern Detection
- Cascade Prediction
- Anomaly Scoring

### Phase 3 — Predictive Intelligence

Forecasts:

- ETA to SLA breach
- queue saturation risk
- throughput collapse risk

Supports intervention simulation:

- increase staffing
- extend processing hours
- adjust queue thresholds

### Phase 4 — Recommendation Intelligence

Each recommendation includes:

- confidence score
- metric grounding
- incident linkage
- historical effectiveness comparison

Outputs remain auditable and explainable.

### Phase 5 — Human-in-the-Loop Investigation Agent

Groq-powered investigation agent analyzes incidents using structured system tools.

Agent tools:

- check_health_scores
- get_open_incidents
- get_cascade_predictions
- get_eta_to_breach
- get_recurring_patterns

The agent proposes actions but never executes changes automatically.

---

## Authentication & User Isolation

Supabase Auth provides:

- email/password login
- JWT session validation
- per-user dataset isolation
- personal webhook API keys

---

## Connect Your System (Webhook Ingestion)

Endpoint:

POST `/webhook/events`

Supports ingestion from:

- Python services
- cron jobs
- schedulers
- internal workflow trackers
- monitoring pipelines

Duplicate incident correlation reduces alert noise automatically.

---

## Free Live Public Connectors

Endpoint:

POST `/fetch-live-data?industry=`

Supported industries:

| Industry | Endpoint Key | Live Support |
|---|---|---|
| Healthcare | healthcare | Yes |
| Airport | airport | Yes |
| Weather | weather | Yes |
| Energy | energy | Optional (API key) |
| Water | water | Optional (API key) |

Response modes returned by the platform:

- Live Data
- Fallback Demo Data
- Demo Data

---

## File Upload With AI Column Mapping

Upload:

- CSV
- Excel

The platform automatically detects:

- queue size
- processing time
- throughput
- workflow stage names

No template required.

---

## Audit Trail

Tracks:

- AI investigations
- incident analyses
- recommendations
- resolution outcomes
- decision timestamps

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js + TypeScript + Tailwind |
| Backend | FastAPI |
| Database | Supabase PostgreSQL |
| Auth | Supabase Auth |
| AI | Groq |
| Agent | Groq tool-calling |
| Parsing | openpyxl + python-multipart |
| Public Data | CMS + FAA + NOAA (+ optional EIA + USGS) |
| Frontend Hosting | Vercel |
| Backend Hosting | Render |
| CI/CD | GitHub → Vercel + Render |

---

## API Reference

### Core

GET `/health`  
GET `/auth/me`  
GET `/incidents`  
GET `/incidents/stats`  
PATCH `/incidents/{id}/resolve`  
POST `/analyze-incident/{id}`  
POST `/incidents/{id}/outcome`

### Intelligence Engine

GET `/intelligence/health-scores`  
GET `/intelligence/recurring-patterns`  
GET `/intelligence/cascade-predictions`  
GET `/intelligence/anomaly-scores`  
GET `/intelligence/eta-to-breach`  
GET `/intelligence/capacity-forecast`  
GET `/intelligence/whatif-simulation`  
GET `/intelligence/resolution-effectiveness`  
GET `/intelligence/playbook/{stage}`

### AI Agent

POST `/agent/investigate`  
POST `/agent/decision`

### Data Ingestion

POST `/webhook/events`  
POST `/test-webhook`  
GET `/connect-info`  
POST `/analyze-custom`  
POST `/extract-and-analyze`  
POST `/fetch-live-data`

---

## Database Schema

```
incidents
workflow_metrics
analysis_logs
incident_outcomes
recommendations
suggestions
user_api_keys
```

---

## Built By

Kushal Jain

Frontend  
https://ops-intelligence-platform.vercel.app

Backend API  
https://ops-intelligence-platform.onrender.com/docs

GitHub  
https://github.com/kushaljaink/ops-intelligence-platform
>>>>>>> d3ab4f3 (Normalize README formatting)
