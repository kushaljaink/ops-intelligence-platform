# Ops Intelligence Platform - Project Documentation

## Production Snapshot

- Frontend: Next.js 16 on Vercel
- Backend: FastAPI on Render
- Database/Auth: Supabase
- AI: Groq
- Live connector orchestration: `backend/services/live_data_service.py`

## Live Industry Matrix

| Industry | Key | Source | Free requirement | Behavior |
|---|---|---|---|---|
| Energy | `energy` | U.S. EIA API | free `EIA_API_KEY` | live first, fallback on error |
| Water | `water` | USGS Water Services | `USGS_API_KEY` optional | live first, fallback on error |
| Weather | `weather` | NOAA / NWS Alerts | no paid key | live first, fallback on error |
| Airport | `airport` | FAA public delays/NAS status | `FAA_ENABLED=true` | live first, fallback on error |
| Healthcare | `healthcare` | CMS public provider data | none required | live first, fallback on error |

Demo-only industries continue to use seeded data and existing intelligence logic.

## Connector Rules

All live ingestion is deterministic and rule-based. No LLMs are used for source ingestion.

- Energy: demand spike, generation shortfall, interchange anomaly
- Water: above-threshold level, rapid rise
- Weather: alert type + severity/urgency
- Airport: ground stop, closure, major delay/TMI
- Healthcare: ED operational strain from public CMS measures

Helpers implemented in the live service:

- `classify_severity_from_signal`
- `build_incident_record`
- `safe_float`
- `safe_str`
- `parse_timestamp`

## Fallback Design

If a live source fails, rate-limits, or cannot be used because a required env var is missing:

- the backend logs the error
- deterministic fallback incidents are returned
- response metadata uses `data_mode = fallback`
- the dashboard remains usable

Successful source fetches use `data_mode = live`.

## API

### `POST /fetch-live-data`

Supported industries:

- `energy`
- `water`
- `weather`
- `airport`
- `healthcare`
- `all`

For `all`, the backend continues even if one connector fails and returns per-industry summaries.

## Frontend Behavior

- Live-supported industries are labeled `Hybrid`
- Demo-only industries are labeled `Demo`
- The header shows whether the current view is using:
  - `Live Data`
  - `Refreshing Live Data`
  - `Fallback Demo Data`
  - `Demo Data`

## Required/Optional Env Vars

Backend:

- `SUPABASE_URL`
- `SUPABASE_KEY`
- `GROQ_API_KEY`
- `SUPABASE_JWT_SECRET`
- `EIA_API_KEY`
- `USGS_API_KEY` optional
- `NOAA_USER_AGENT`
- `FAA_ENABLED`

Frontend:

- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`

## Intentionally Skipped

Not used by design:

- TomTom
- paid traffic APIs
- paid aviation APIs
- commercial weather vendors
- any source that requires billing setup
