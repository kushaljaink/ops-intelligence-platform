# Ops Intelligence Platform

AI-powered workflow monitoring, bottleneck detection, and operational intelligence across multiple industries.

## Current Live Data Coverage

Live-supported industries backed only by free official/public sources:

| Industry | Key | Source | Env vars | Mode |
|---|---|---|---|---|
| Energy | `energy` | U.S. EIA API | `EIA_API_KEY` | Hybrid |
| Water | `water` | USGS Water Services | `USGS_API_KEY` optional | Hybrid |
| Weather | `weather` | NOAA / NWS Alerts API | `NOAA_USER_AGENT` recommended | Hybrid |
| Airport | `airport` | FAA delays / NAS status page | `FAA_ENABLED` optional | Hybrid |
| Healthcare | `healthcare` | CMS Provider Data API | none required | Hybrid |

`Hybrid` means the app attempts live refresh first and gracefully falls back to demo-style incidents if the source fails, rate-limits, or is not configured.

Demo-only industries remain available with seeded data and the existing intelligence features:
`cruise`, `banking`, `ecommerce`, `construction`, `civil`, `architecture`, `traffic`, `telecom`, `manufacturing`, `retail`, `food`, `pharma`, `government`, `realestate`, `education`, `media`, and `custom`.

## Architecture

- Frontend: Next.js 16 + React 19 + TypeScript
- Backend: FastAPI
- Database/Auth: Supabase
- AI analysis + agent: Groq
- Live data orchestration: `backend/services/live_data_service.py`
- Shared connector CLI: `real_data_connectors.py`

## Free-Only Live Sources

The project intentionally avoids paid vendors, trials, or freemium lock-in.

- Energy uses the free U.S. EIA API.
- Water uses USGS Water Services. `USGS_API_KEY` is optional and mainly useful for higher-volume usage.
- Weather uses NOAA / National Weather Service Alerts. No paid vendor is used.
- Airport uses official FAA public status data. No commercial aviation provider is used.
- Healthcare uses CMS public provider performance data.

Intentionally skipped:

- TomTom
- commercial traffic APIs
- paid aviation APIs
- any vendor that requires billing setup

## Fallback Behavior

For live-supported industries, the backend never lets a source outage break the app.

If a source:

- fails
- rate-limits
- returns malformed data
- requires a missing env var

then the backend:

- logs the failure
- returns deterministic fallback incidents
- tags the response with `data_mode = fallback`
- keeps the dashboard usable instead of failing hard

If live fetch succeeds, returned incident metadata is tagged with `data_mode = live`.

## Local Development

### Prerequisites

- Python 3.11+
- Node.js 20+
- Supabase project
- Groq API key

### 1. Clone and install

```powershell
git clone https://github.com/kushaljaink/ops-intelligence-platform
cd ops-intelligence-platform
```

### 2. Backend setup

```powershell
cd backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

Create `backend/.env`:

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_service_role_key
GROQ_API_KEY=your_groq_key
SUPABASE_JWT_SECRET=your_supabase_jwt_secret
RESEND_API_KEY=
ALERT_EMAIL=
SLACK_WEBHOOK_URL=
WEBHOOK_SECRET=
EIA_API_KEY=
USGS_API_KEY=
NOAA_USER_AGENT=OpsIntelligence/1.0 (your-email@example.com)
FAA_ENABLED=true
```

Run the API:

```powershell
uvicorn main:app --reload
```

Backend runs on `http://localhost:8000`.

### 3. Frontend setup

```powershell
cd ..\frontend
npm install
```

Create `frontend/.env.local`:

```env
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_supabase_anon_key
```

Run the frontend:

```powershell
npm run dev
```

Frontend runs on `http://localhost:3000`.

## Deployment Env Vars

### Render backend

Set:

- `SUPABASE_URL`
- `SUPABASE_KEY`
- `GROQ_API_KEY`
- `SUPABASE_JWT_SECRET`
- `RESEND_API_KEY` optional
- `ALERT_EMAIL` optional
- `SLACK_WEBHOOK_URL` optional
- `WEBHOOK_SECRET` optional
- `EIA_API_KEY`
- `USGS_API_KEY` optional
- `NOAA_USER_AGENT`
- `FAA_ENABLED`

### Vercel frontend

Set:

- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`

## Live Fetch Endpoint

The dashboard calls:

```http
POST /fetch-live-data?industry=<industry>
```

Supported values:

- `energy`
- `water`
- `weather`
- `airport`
- `healthcare`
- `all`

`all` continues processing even if one source fails.

Response shape:

```json
{
  "success": true,
  "industry": "energy",
  "data_mode": "live",
  "incident_count": 2,
  "incidents": [],
  "summary": {}
}
```

## Sample curl Commands

Fetch one live industry:

```bash
curl -X POST "http://localhost:8000/fetch-live-data?industry=energy"
```

Fetch all live industries:

```bash
curl -X POST "http://localhost:8000/fetch-live-data?industry=all"
```

Send your own webhook metrics:

```bash
curl -X POST "http://localhost:8000/webhook/events" \
  -H "Content-Type: application/json" \
  -d '{
    "events": [
      {
        "stage": "ed_triage",
        "queue_size": 28,
        "processing_time_seconds": 3200,
        "throughput": 4,
        "industry": "healthcare"
      }
    ]
  }'
```

Run the shared connector CLI in dry-run mode:

```powershell
python real_data_connectors.py --industry weather --dry-run
python real_data_connectors.py --all --dry-run
```

## Important Notes

- `EIA_API_KEY` is free to obtain from EIA.
- `USGS_API_KEY` is optional; low-volume usage works without it when USGS allows anonymous access.
- NOAA / NWS does not require a paid key, but a descriptive `NOAA_USER_AGENT` is recommended.
- FAA is sourced from official public FAA data only.
- Seeded demo incidents and existing product features remain intact.

## Verification Checklist

1. Start backend and frontend locally.
2. Open the dashboard and switch to `healthcare`, `airport`, `energy`, `water`, and `weather`.
3. Confirm the status chip changes to either `Live Data` or `Fallback Demo Data`.
4. Call `POST /fetch-live-data?industry=all` and verify you get per-industry result summaries.
5. Confirm demo-only industries still load without trying live refresh.
6. Run `python real_data_connectors.py --all --dry-run` and inspect the normalized incident payloads.
7. Temporarily unset `EIA_API_KEY` and verify `energy` falls back instead of crashing.
8. Confirm existing AI analysis, playbooks, agent investigation, and webhook ingestion still work.

Detailed request/response examples and manual checks are in [LIVE_DATA_VERIFICATION.md](/c:/Users/Kushal%20Jain/ops-intelligence-platform/LIVE_DATA_VERIFICATION.md).
