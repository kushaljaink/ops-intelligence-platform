from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import List, Optional
import os
import httpx
from supabase import create_client
from datetime import datetime, timezone, timedelta
from collections import defaultdict

load_dotenv()

app = FastAPI(title="Ops Intelligence Platform")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://ops-intelligence-platform.vercel.app"],
    allow_methods=["*"],
    allow_headers=["*"],
)

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
RESEND_API_KEY = os.getenv("RESEND_API_KEY")
ALERT_EMAIL = os.getenv("ALERT_EMAIL", "")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")

INDUSTRY_THRESHOLDS = {
    "cruise":     {"queue": 50,  "processing": 300, "throughput": 10},
    "healthcare": {"queue": 20,  "processing": 120, "throughput": 15},
    "banking":    {"queue": 100, "processing": 600, "throughput": 5},
    "ecommerce":  {"queue": 200, "processing": 180, "throughput": 50},
    "airport":    {"queue": 80,  "processing": 240, "throughput": 20},
}

DAY_NAMES = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]


# ─── Groq helper ─────────────────────────────────────────────────────────────

async def call_groq(prompt: str) -> str:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 500,
            },
        )
        if response.status_code == 429:
            raise HTTPException(
                status_code=429,
                detail="GROQ_RATE_LIMIT: The AI service is temporarily rate limited. Please wait 60 seconds and try again.",
            )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]


# ─── Email helper ─────────────────────────────────────────────────────────────

async def send_alert_email(incident: dict):
    if not RESEND_API_KEY or not ALERT_EMAIL:
        return
    async with httpx.AsyncClient(timeout=10.0) as client:
        await client.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
            json={
                "from": "alerts@ops-intelligence.app",
                "to": [ALERT_EMAIL],
                "subject": f"🚨 HIGH Severity Incident: {incident.get('stage', 'Unknown')}",
                "html": f"""
                    <h2>High Severity Incident Detected</h2>
                    <p><strong>Stage:</strong> {incident.get('stage')}</p>
                    <p><strong>Severity:</strong> {incident.get('severity', '').upper()}</p>
                    <p><strong>Industry:</strong> {incident.get('industry', 'N/A')}</p>
                    <p><strong>Description:</strong> {incident.get('description')}</p>
                    <p><strong>Detected at:</strong> {incident.get('created_at')}</p>
                    <hr/>
                    <p><a href="https://ops-intelligence-platform.vercel.app">View Dashboard →</a></p>
                """,
            },
        )


# ─── Core routes ─────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "Ops Intelligence Platform"}


@app.get("/incidents")
def get_incidents(industry: str = "cruise"):
    response = (
        supabase.table("incidents")
        .select("*")
        .eq("industry", industry)
        .order("created_at", desc=True)
        .execute()
    )
    return {"incidents": response.data}


@app.get("/incidents/stats")
def get_stats(industry: str = "cruise"):
    all_resp = (
        supabase.table("incidents")
        .select("id, severity, status, created_at")
        .eq("industry", industry)
        .execute()
    )
    incidents = all_resp.data or []
    now = datetime.now(timezone.utc)

    today_count = sum(
        1 for i in incidents
        if i.get("created_at") and
        (now - datetime.fromisoformat(i["created_at"].replace("Z", "+00:00"))).days < 1
    )
    yesterday_count = sum(
        1 for i in incidents
        if i.get("created_at") and
        1 <= (now - datetime.fromisoformat(i["created_at"].replace("Z", "+00:00"))).days < 2
    )

    return {
        "total": len(incidents),
        "high_severity": sum(1 for i in incidents if i.get("severity") == "high"),
        "open": sum(1 for i in incidents if i.get("status") == "open"),
        "today_count": today_count,
        "yesterday_count": yesterday_count,
        "trend": today_count - yesterday_count,
    }


@app.patch("/incidents/{incident_id}/resolve")
def resolve_incident(incident_id: str):
    result = supabase.table("incidents").select("*").eq("id", incident_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Incident not found")
    supabase.table("incidents").update({
        "status": "resolved",
        "resolved_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", incident_id).execute()
    return {"success": True, "incident_id": incident_id, "status": "resolved"}


@app.get("/incidents/{incident_id}/analysis-history")
def get_analysis_history(incident_id: str):
    response = (
        supabase.table("analysis_logs")
        .select("*")
        .eq("incident_id", incident_id)
        .order("created_at", desc=True)
        .execute()
    )
    return {"history": response.data}


@app.get("/incidents/{incident_id}/recommendations")
def get_recommendations(incident_id: str):
    response = supabase.table("recommendations").select("*").eq("incident_id", incident_id).execute()
    return {"recommendations": response.data}


@app.get("/workflow-events")
def get_workflow_events():
    response = supabase.table("workflow_events").select("*").order("created_at", desc=True).execute()
    return {"events": response.data}


@app.post("/analyze-incident/{incident_id}")
async def analyze_incident(incident_id: str):
    result = supabase.table("incidents").select("*").eq("id", incident_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Incident not found")

    incident = result.data
    industry = incident.get("industry", "operations")

    prompt = (
        f"You are a senior operations analyst reviewing a live incident in a {industry} operation.\n\n"
        f"Incident details:\n"
        f"- Stage: {incident.get('stage', 'N/A')}\n"
        f"- Severity: {incident.get('severity', 'N/A')}\n"
        f"- Status: {incident.get('status', 'N/A')}\n"
        f"- Description: {incident.get('description', 'N/A')}\n\n"
        "Your job:\n"
        "1. Identify the root cause based on the description\n"
        "2. Explain the downstream impact if not addressed immediately\n"
        "3. Give 3 specific, numbered actions the ops team should take in the next 30 minutes\n\n"
        f"Use {industry}-appropriate language. Be direct, specific, and urgent. No generic advice."
    )

    analysis = await call_groq(prompt)

    supabase.table("analysis_logs").insert({
        "incident_id": incident_id,
        "ai_analysis": analysis,
        "triggered_by": "user",
    }).execute()

    if incident.get("severity") == "high":
        await send_alert_email(incident)

    return {
        "incident_id": incident_id,
        "stage": incident.get("stage"),
        "severity": incident.get("severity"),
        "ai_analysis": analysis,
    }


# ─── Custom analysis ──────────────────────────────────────────────────────────

class WorkflowRow(BaseModel):
    stage: str
    queue_size: float
    processing_time_seconds: float
    throughput: float


class AnalyzeCustomRequest(BaseModel):
    rows: List[WorkflowRow]
    industry: str = "operations"


@app.post("/analyze-custom")
async def analyze_custom(body: AnalyzeCustomRequest):
    rows = body.rows
    if not rows:
        raise HTTPException(status_code=400, detail="No workflow data provided")

    thresholds = INDUSTRY_THRESHOLDS.get(body.industry, {"queue": 50, "processing": 300, "throughput": 10})

    issues = []
    for r in rows:
        row_issues = []
        if r.queue_size > thresholds["queue"]:
            row_issues.append(f"queue backed up ({r.queue_size} items, threshold: {thresholds['queue']})")
        if r.processing_time_seconds > thresholds["processing"]:
            row_issues.append(f"processing time too high ({r.processing_time_seconds}s, threshold: {thresholds['processing']}s)")
        if r.throughput < thresholds["throughput"]:
            row_issues.append(f"throughput critically low ({r.throughput}/hr, threshold: {thresholds['throughput']}/hr)")
        if row_issues:
            issues.append({"stage": r.stage, "issues": row_issues})

    rows_text = "\n".join(
        f"- Stage: {r.stage} | Queue: {r.queue_size} | Processing time: {r.processing_time_seconds}s | Throughput: {r.throughput}/hr"
        for r in rows
    )
    issues_text = "\n".join(
        f"- {i['stage']}: {', '.join(i['issues'])}" for i in issues
    ) if issues else "No threshold violations detected."

    prompt = (
        f"You are a senior operations analyst reviewing live workflow metrics for a {body.industry} operation.\n\n"
        f"Workflow data ({len(rows)} stages):\n{rows_text}\n\n"
        f"Rule-based threshold violations:\n{issues_text}\n\n"
        "Your job:\n"
        "1. Identify the single worst bottleneck and explain WHY using the actual numbers\n"
        "2. Explain how it cascades to affect other stages downstream\n"
        "3. Give 3 specific, numbered actions the ops team should take in the next 30 minutes\n\n"
        f"Use {body.industry}-appropriate language. Reference actual metric values — no generic advice."
    )

    ai_analysis = await call_groq(prompt)
    return {"detected_issues": issues, "ai_analysis": ai_analysis}


# ─── Phase 2: Pattern Intelligence ───────────────────────────────────────────

@app.get("/intelligence/health-scores")
def get_health_scores(industry: str = "cruise"):
    """
    Current health score per stage based on last 3 readings.
    Returns 0-100 score + trend (improving/degrading/stable).
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    response = (
        supabase.table("workflow_metrics")
        .select("stage, health_score, recorded_at")
        .eq("industry", industry)
        .gte("recorded_at", cutoff)
        .order("recorded_at", desc=True)
        .execute()
    )

    # Group by stage, take last 3 readings
    stage_readings: dict = defaultdict(list)
    for row in response.data:
        stage_readings[row["stage"]].append(row["health_score"])

    results = []
    for stage, scores in stage_readings.items():
        recent = scores[:3]
        current = recent[0] if recent else 0
        avg = sum(recent) / len(recent)

        # Trend: compare first and last of recent readings
        if len(recent) >= 2:
            diff = recent[0] - recent[-1]
            if diff > 5:
                trend = "degrading"
            elif diff < -5:
                trend = "improving"
            else:
                trend = "stable"
        else:
            trend = "stable"

        # Status label
        if current >= 80:
            status = "healthy"
        elif current >= 60:
            status = "warning"
        elif current >= 40:
            status = "critical"
        else:
            status = "severe"

        results.append({
            "stage": stage,
            "health_score": round(current, 1),
            "avg_24h": round(avg, 1),
            "trend": trend,
            "status": status,
        })

    results.sort(key=lambda x: x["health_score"])
    return {"health_scores": results, "industry": industry}


@app.get("/intelligence/recurring-patterns")
def get_recurring_patterns(industry: str = "cruise"):
    """
    Detect stages that breach thresholds repeatedly.
    Identifies time-of-day and day-of-week patterns.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    thresholds = INDUSTRY_THRESHOLDS.get(industry, {"queue": 50, "processing": 300, "throughput": 10})

    response = (
        supabase.table("workflow_metrics")
        .select("stage, queue_size, processing_time_seconds, throughput, health_score, recorded_at")
        .eq("industry", industry)
        .gte("recorded_at", cutoff)
        .execute()
    )

    # Find breach events
    stage_breaches: dict = defaultdict(list)
    for row in response.data:
        breached = (
            row["queue_size"] > thresholds["queue"] or
            row["processing_time_seconds"] > thresholds["processing"] or
            row["throughput"] < thresholds["throughput"]
        )
        if breached:
            ts = datetime.fromisoformat(row["recorded_at"].replace("Z", "+00:00"))
            stage_breaches[row["stage"]].append({
                "hour": ts.hour,
                "dow": int(ts.strftime("%w")),  # 0=Sun
                "health": row["health_score"],
            })

    patterns = []
    for stage, breaches in stage_breaches.items():
        if len(breaches) < 3:
            continue

        # Find peak hour
        hour_counts: dict = defaultdict(int)
        dow_counts: dict = defaultdict(int)
        for b in breaches:
            hour_counts[b["hour"]] += 1
            dow_counts[b["dow"]] += 1

        peak_hour = max(hour_counts, key=lambda h: hour_counts[h])
        peak_dow = max(dow_counts, key=lambda d: dow_counts[d])
        peak_hour_pct = round(hour_counts[peak_hour] / len(breaches) * 100)
        peak_dow_pct = round(dow_counts[peak_dow] / len(breaches) * 100)
        avg_health = round(sum(b["health"] for b in breaches) / len(breaches), 1)

        # Format hour nicely
        hour_label = f"{'12' if peak_hour == 12 else peak_hour % 12 or 12}{'am' if peak_hour < 12 else 'pm'}"

        insight = f"{stage.replace('_', ' ').title()} has breached thresholds {len(breaches)} times in 30 days"
        if peak_hour_pct >= 40:
            insight += f", most often around {hour_label} ({peak_hour_pct}% of failures)"
        if peak_dow_pct >= 40:
            insight += f" on {DAY_NAMES[peak_dow]}s ({peak_dow_pct}% of failures)"

        patterns.append({
            "stage": stage,
            "breach_count": len(breaches),
            "avg_health_during_breach": avg_health,
            "peak_hour": peak_hour,
            "peak_hour_label": hour_label,
            "peak_hour_pct": peak_hour_pct,
            "peak_dow": peak_dow,
            "peak_dow_label": DAY_NAMES[peak_dow],
            "peak_dow_pct": peak_dow_pct,
            "insight": insight,
            "severity": "high" if len(breaches) > 20 else "medium" if len(breaches) > 10 else "low",
        })

    patterns.sort(key=lambda x: x["breach_count"], reverse=True)
    return {"patterns": patterns, "industry": industry, "days_analyzed": 30}


@app.get("/intelligence/cascade-predictions")
def get_cascade_predictions(industry: str = "cruise"):
    """
    Detect cascade relationships between stages.
    If stage A is unhealthy, does stage B degrade 2hrs later?
    Returns predictions with confidence scores.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    thresholds = INDUSTRY_THRESHOLDS.get(industry, {"queue": 50, "processing": 300, "throughput": 10})

    response = (
        supabase.table("workflow_metrics")
        .select("stage, queue_size, processing_time_seconds, throughput, health_score, recorded_at")
        .eq("industry", industry)
        .gte("recorded_at", cutoff)
        .order("recorded_at")
        .execute()
    )

    # Group readings by stage and time bucket (2hr windows)
    stage_buckets: dict = defaultdict(dict)
    for row in response.data:
        ts = datetime.fromisoformat(row["recorded_at"].replace("Z", "+00:00"))
        bucket = ts.replace(minute=0, second=0, microsecond=0)
        bucket_key = bucket.isoformat()
        breached = (
            row["queue_size"] > thresholds["queue"] or
            row["processing_time_seconds"] > thresholds["processing"] or
            row["throughput"] < thresholds["throughput"]
        )
        stage_buckets[row["stage"]][bucket_key] = {
            "health": row["health_score"],
            "breached": breached,
        }

    stages = list(stage_buckets.keys())
    predictions = []

    # Check all stage pairs for cascade correlation
    for source in stages:
        for target in stages:
            if source == target:
                continue

            source_data = stage_buckets[source]
            target_data = stage_buckets[target]

            # Check if source breach → target breach 2hrs later
            cascade_count = 0
            source_breach_count = 0

            for bucket_key, reading in source_data.items():
                if not reading["breached"]:
                    continue
                source_breach_count += 1

                # Look for target breach 2hrs later
                ts = datetime.fromisoformat(bucket_key)
                future_ts = (ts + timedelta(hours=2)).isoformat()
                future_reading = target_data.get(future_ts)
                if future_reading and future_reading["breached"]:
                    cascade_count += 1

            if source_breach_count < 5:
                continue

            confidence = round(cascade_count / source_breach_count * 100)
            if confidence < 40:
                continue

            # Check if source is currently stressed
            recent_source = sorted(source_data.keys())[-3:]
            source_currently_stressed = any(
                source_data[k]["breached"] for k in recent_source
            )

            predictions.append({
                "source_stage": source,
                "target_stage": target,
                "confidence": confidence,
                "cascade_count": cascade_count,
                "source_breach_count": source_breach_count,
                "lag_hours": 2,
                "source_currently_stressed": source_currently_stressed,
                "insight": (
                    f"When {source.replace('_', ' ').title()} breaches thresholds, "
                    f"{target.replace('_', ' ').title()} degrades {2}hrs later "
                    f"{confidence}% of the time ({cascade_count}/{source_breach_count} occurrences)"
                ),
                "alert": source_currently_stressed and confidence >= 60,
            })

    predictions.sort(key=lambda x: (x["alert"], x["confidence"]), reverse=True)
    return {"predictions": predictions[:6], "industry": industry}


@app.get("/intelligence/anomaly-scores")
def get_anomaly_scores(industry: str = "cruise"):
    """
    Score each stage 0-100 on current health vs 30-day baseline.
    A stage at 78 is trending bad before it hits the threshold.
    """
    cutoff_30d = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    cutoff_24h = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()

    all_resp = (
        supabase.table("workflow_metrics")
        .select("stage, health_score, recorded_at")
        .eq("industry", industry)
        .gte("recorded_at", cutoff_30d)
        .execute()
    )

    stage_all: dict = defaultdict(list)
    stage_recent: dict = defaultdict(list)

    for row in all_resp.data:
        stage_all[row["stage"]].append(row["health_score"])
        if row["recorded_at"] >= cutoff_24h:
            stage_recent[row["stage"]].append(row["health_score"])

    scores = []
    for stage in stage_all:
        baseline_avg = sum(stage_all[stage]) / len(stage_all[stage])
        baseline_min = min(stage_all[stage])

        recent = stage_recent.get(stage, stage_all[stage][-3:])
        recent_avg = sum(recent) / len(recent)

        # Anomaly = how far current is from baseline, normalized
        deviation = baseline_avg - recent_avg
        anomaly_score = round(min(100, max(0, (deviation / max(baseline_avg, 1)) * 100 * 2)), 1)

        scores.append({
            "stage": stage,
            "current_health": round(recent_avg, 1),
            "baseline_health": round(baseline_avg, 1),
            "deviation": round(deviation, 1),
            "anomaly_score": anomaly_score,
            "flag": anomaly_score > 30,
            "insight": (
                f"{stage.replace('_', ' ').title()} is running "
                f"{round(deviation, 1)} points below its 30-day average "
                f"({round(recent_avg, 1)} vs baseline {round(baseline_avg, 1)})"
                if deviation > 5 else
                f"{stage.replace('_', ' ').title()} is performing normally"
            )
        })

    scores.sort(key=lambda x: x["anomaly_score"], reverse=True)
    return {"anomaly_scores": scores, "industry": industry}


# ─── Webhook ──────────────────────────────────────────────────────────────────

class WebhookEvent(BaseModel):
    stage: str
    queue_size: float
    processing_time_seconds: float
    throughput: float
    industry: str = "operations"
    source: Optional[str] = "webhook"


class WebhookPayload(BaseModel):
    events: List[WebhookEvent]
    secret: Optional[str] = None


@app.post("/webhook/events")
async def receive_webhook(payload: WebhookPayload):
    if WEBHOOK_SECRET and payload.secret != WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Invalid webhook secret")

    created_incidents = []
    triggered_analyses = []

    for event in payload.events:
        industry = event.industry
        thresholds = INDUSTRY_THRESHOLDS.get(industry, {"queue": 50, "processing": 300, "throughput": 10})

        violations = []
        if event.queue_size > thresholds["queue"]:
            violations.append(f"Queue size {event.queue_size} exceeds threshold of {thresholds['queue']}")
        if event.processing_time_seconds > thresholds["processing"]:
            violations.append(f"Processing time {event.processing_time_seconds}s exceeds threshold of {thresholds['processing']}s")
        if event.throughput < thresholds["throughput"]:
            violations.append(f"Throughput {event.throughput}/hr below threshold of {thresholds['throughput']}/hr")

        # Always log to metrics table
        thresholds_val = INDUSTRY_THRESHOLDS.get(industry, {"queue": 50, "processing": 300, "throughput": 10})
        health = max(0, min(100,
            100
            - (event.queue_size / thresholds_val["queue"] * 30)
            - (event.processing_time_seconds / thresholds_val["processing"] * 30)
            + (min(event.throughput, thresholds_val["throughput"]) / thresholds_val["throughput"] * 10)
        ))
        supabase.table("workflow_metrics").insert({
            "industry": industry,
            "stage": event.stage,
            "queue_size": event.queue_size,
            "processing_time_seconds": event.processing_time_seconds,
            "throughput": event.throughput,
            "health_score": round(health, 1),
        }).execute()

        if violations:
            severity = "high" if len(violations) >= 2 else "medium"
            description = ". ".join(violations)
            incident_resp = supabase.table("incidents").insert({
                "stage": event.stage,
                "severity": severity,
                "description": description,
                "status": "open",
                "industry": industry,
            }).execute()

            if incident_resp.data:
                incident = incident_resp.data[0]
                created_incidents.append(incident)
                if severity == "high":
                    try:
                        prompt = (
                            f"HIGH severity incident auto-detected in {industry} operation.\n"
                            f"Stage: {event.stage} | Queue: {event.queue_size} | "
                            f"Processing: {event.processing_time_seconds}s | Throughput: {event.throughput}/hr\n"
                            f"Violations: {description}\n"
                            "Give immediate root cause and 3 urgent actions. Be concise."
                        )
                        analysis = await call_groq(prompt)
                        supabase.table("analysis_logs").insert({
                            "incident_id": incident["id"],
                            "ai_analysis": analysis,
                            "triggered_by": "webhook_auto",
                        }).execute()
                        triggered_analyses.append(incident["id"])
                        await send_alert_email(incident)
                    except Exception:
                        pass

    return {
        "received": len(payload.events),
        "incidents_created": len(created_incidents),
        "auto_analyzed": len(triggered_analyses),
    }
