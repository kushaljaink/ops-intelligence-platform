# Live Data Verification

## Sample Requests

Single industry:

```bash
curl -X POST "http://localhost:8000/fetch-live-data?industry=energy"
```

All live-supported industries:

```bash
curl -X POST "http://localhost:8000/fetch-live-data?industry=all"
```

Dry-run connector output:

```powershell
python real_data_connectors.py --all --dry-run
python real_data_connectors.py --industry weather --dry-run
```

## Expected Response Shape

Single industry:

```json
{
  "success": true,
  "industry": "energy",
  "data_mode": "live",
  "incident_count": 2,
  "incidents": [],
  "summary": {
    "supported_live_industries": ["healthcare", "airport", "energy", "water", "weather"],
    "industry_result": {
      "supported": true,
      "data_mode": "live",
      "incident_count": 2,
      "metric_count": 2,
      "stored_incident_count": 2,
      "source_systems": ["U.S. Energy Information Administration"],
      "source_system": "U.S. Energy Information Administration",
      "error": null,
      "fetched_at": "2026-03-22T21:00:00+00:00",
      "incidents": []
    }
  }
}
```

All industries:

```json
{
  "success": true,
  "industry": "all",
  "data_mode": "mixed",
  "incident_count": 6,
  "incidents": [],
  "summary": {
    "supported_live_industries": ["healthcare", "airport", "energy", "water", "weather"],
    "mode_counts": {
      "live": 3,
      "fallback": 2
    },
    "industries": {}
  }
}
```

## What Live Mode Looks Like

- `data_mode` is `live`
- `summary.industry_result.error` is `null`
- `source_system` is populated
- `fetched_at` is populated
- UI shows `Hybrid` support and `Live Data` status

## What Fallback Mode Looks Like

- `data_mode` is `fallback`
- `summary.industry_result.error` explains the failed source or missing env var
- `metadata.data_mode` on each incident is `fallback`
- UI shows `Fallback Demo Data`
- UI notice: `Live source unavailable. Showing fallback demo scenario.`

## Manual Verification Checklist

1. Start the backend and frontend locally.
2. Open the dashboard and switch to `healthcare`, `airport`, `energy`, `water`, and `weather`.
3. Confirm each live-supported industry pill shows `Live`.
4. Confirm demo-only industries show `Demo`.
5. Confirm the header shows:
   - support mode: `Hybrid` or `Demo`
   - current status: `Live Data`, `Fallback Demo Data`, or `Demo Data`
6. Confirm source system and fetch timestamp appear after a live or fallback refresh.
7. Remove `EIA_API_KEY` and verify `energy` returns `fallback` without breaking the page.
8. Call `POST /fetch-live-data?industry=all` and confirm per-industry counts and mixed-mode summary if one source falls back.
9. Confirm existing incident analysis, agent investigation, and webhook features still work.
