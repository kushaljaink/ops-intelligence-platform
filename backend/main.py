from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import List, Optional
import os
import re
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

ACTION_CATEGORIES = {
    "staff": "staffing",
    "hire": "staffing",
    "personnel": "staffing",
    "team": "staffing",
    "equip": "equipment",
    "machine": "equipment",
    "hardware": "equipment",
    "system": "equipment",
    "process": "process",
    "procedure": "process",
    "workflow": "process",
    "escalat": "escalation",
    "manag": "escalation",
    "supervis": "escalation",
}


# ─── Helpers ─────────────────────────────────────────────────────────────────

async def call_groq(prompt: str, max_tokens: int = 500) -> str:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
            },
        )
        if response.status_code == 429:
            raise HTTPException(status_code=429, detail="GROQ_RATE_LIMIT: Rate limited. Wait 60s.")
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]


def extract_confidence(text: str) -> tuple[int, str]:
    """
    Extract confidence score from AI analysis text.
    Looks for explicit percentages or infers from language cues.
    Returns (score 0-100, reason string).
    """
    # Look for explicit confidence mentions
    explicit = re.search(r'(\d{1,3})\s*%\s*confiden', text, re.IGNORECASE)
    if explicit:
        score = min(100, max(0, int(explicit.group(1))))
        return score, f"Explicitly stated {score}% confidence in analysis"

    # Infer from language
    text_lower = text.lower()
    high_confidence_words = ["clearly", "definitely", "certainly", "obvious", "evident", "undoubtedly", "strongly indicates"]
    medium_confidence_words = ["likely", "probably", "suggests", "appears", "seems", "indicates"]
    low_confidence_words = ["possibly", "may", "might", "unclear", "uncertain", "hard to determine", "could be"]

    high_count = sum(1 for w in high_confidence_words if w in text_lower)
    medium_count = sum(1 for w in medium_confidence_words if w in text_lower)
    low_count = sum(1 for w in low_confidence_words if w in text_lower)

    if high_count >= 2:
        return 88, "Analysis uses high-certainty language"
    elif high_count == 1 and low_count == 0:
        return 80, "Analysis shows strong directional confidence"
    elif medium_count >= 2 and low_count == 0:
        return 70, "Analysis uses moderately confident language"
    elif low_count >= 2:
        return 45, "Analysis expresses significant uncertainty"
    elif low_count == 1:
        return 60, "Analysis notes some uncertainty"
    else:
        return 72, "Analysis based on available incident data"


def categorize_action(action_text: str) -> str:
    text_lower = action_text.lower()
    for keyword, category in ACTION_CATEGORIES.items():
        if keyword in text_lower:
            return category
    return "other"


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
                "subject": f"🚨 HIGH Severity: {incident.get('stage')}",
                "html": f"<h2>High Severity Incident</h2><p><strong>Stage:</strong> {incident.get('stage')}</p><p><strong>Description:</strong> {incident.get('description')}</p>",
            },
        )


# ─── Core routes ──────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "Ops Intelligence Platform"}


@app.get("/incidents")
def get_incidents(industry: str = "cruise"):
    response = supabase.table("incidents").select("*").eq("industry", industry).order("created_at", desc=True).execute()
    return {"incidents": response.data}


@app.get("/incidents/stats")
def get_stats(industry: str = "cruise"):
    all_resp = supabase.table("incidents").select("id, severity, status, created_at").eq("industry", industry).execute()
    incidents = all_resp.data or []
    now = datetime.now(timezone.utc)
    today_count = sum(1 for i in incidents if i.get("created_at") and (now - datetime.fromisoformat(i["created_at"].replace("Z", "+00:00"))).days < 1)
    yesterday_count = sum(1 for i in incidents if i.get("created_at") and 1 <= (now - datetime.fromisoformat(i["created_at"].replace("Z", "+00:00"))).days < 2)
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
    supabase.table("incidents").update({"status": "resolved", "resolved_at": datetime.now(timezone.utc).isoformat()}).eq("id", incident_id).execute()
    return {"success": True, "incident_id": incident_id, "status": "resolved"}


@app.get("/incidents/{incident_id}/analysis-history")
def get_analysis_history(incident_id: str):
    response = supabase.table("analysis_logs").select("*").eq("incident_id", incident_id).order("created_at", desc=True).execute()
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
        f"- Stage: {incident.get('stage')}\n- Severity: {incident.get('severity')}\n"
        f"- Description: {incident.get('description')}\n\n"
        "1. Identify root cause\n2. Downstream impact\n3. 3 specific actions in next 30 minutes\n"
        f"Use {industry}-appropriate language. No generic advice."
    )

    analysis = await call_groq(prompt)
    confidence_score, confidence_reason = extract_confidence(analysis)

    supabase.table("analysis_logs").insert({
        "incident_id": incident_id,
        "ai_analysis": analysis,
        "triggered_by": "user",
        "confidence_score": confidence_score,
        "confidence_reason": confidence_reason,
    }).execute()

    if incident.get("severity") == "high":
        await send_alert_email(incident)

    return {
        "incident_id": incident_id,
        "stage": incident.get("stage"),
        "severity": incident.get("severity"),
        "ai_analysis": analysis,
        "confidence_score": confidence_score,
        "confidence_reason": confidence_reason,
    }


# ─── Phase 4: Outcome Tracking ────────────────────────────────────────────────

class OutcomePayload(BaseModel):
    action_taken: str
    resolved_in_minutes: Optional[int] = None


@app.post("/incidents/{incident_id}/outcome")
async def log_outcome(incident_id: str, body: OutcomePayload):
    """Log what action was taken after resolving an incident."""
    result = supabase.table("incidents").select("*").eq("id", incident_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Incident not found")

    incident = result.data
    industry = incident.get("industry", "operations")
    stage = incident.get("stage", "")

    # Get health score before (from metrics around incident time)
    incident_time = incident.get("created_at", datetime.now(timezone.utc).isoformat())
    before_resp = (
        supabase.table("workflow_metrics")
        .select("health_score")
        .eq("industry", industry)
        .eq("stage", stage)
        .lte("recorded_at", incident_time)
        .order("recorded_at", desc=True)
        .limit(3)
        .execute()
    )
    health_before = None
    if before_resp.data:
        health_before = sum(r["health_score"] for r in before_resp.data) / len(before_resp.data)

    # Get current health (after)
    after_resp = (
        supabase.table("workflow_metrics")
        .select("health_score")
        .eq("industry", industry)
        .eq("stage", stage)
        .order("recorded_at", desc=True)
        .limit(3)
        .execute()
    )
    health_after = None
    if after_resp.data:
        health_after = sum(r["health_score"] for r in after_resp.data) / len(after_resp.data)

    action_category = categorize_action(body.action_taken)

    outcome = supabase.table("incident_outcomes").insert({
        "incident_id": incident_id,
        "action_taken": body.action_taken,
        "action_category": action_category,
        "health_before": round(health_before, 1) if health_before else None,
        "health_after": round(health_after, 1) if health_after else None,
        "resolved_in_minutes": body.resolved_in_minutes,
    }).execute()

    improvement = None
    if health_before and health_after:
        improvement = round(health_after - health_before, 1)

    return {
        "success": True,
        "action_category": action_category,
        "health_before": round(health_before, 1) if health_before else None,
        "health_after": round(health_after, 1) if health_after else None,
        "improvement": improvement,
        "outcome_id": outcome.data[0]["id"] if outcome.data else None,
    }


@app.get("/incidents/{incident_id}/outcome")
def get_outcome(incident_id: str):
    response = supabase.table("incident_outcomes").select("*").eq("incident_id", incident_id).order("created_at", desc=True).limit(1).execute()
    return {"outcome": response.data[0] if response.data else None}


# ─── Phase 4: Resolution Effectiveness ───────────────────────────────────────

@app.get("/intelligence/resolution-effectiveness")
def get_resolution_effectiveness(industry: str = "cruise"):
    """
    Track recurrence rate per stage.
    A stage that keeps getting resolved but keeps failing = treating symptoms.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()

    all_incidents = (
        supabase.table("incidents")
        .select("id, stage, severity, status, created_at, resolved_at")
        .eq("industry", industry)
        .gte("created_at", cutoff)
        .order("created_at")
        .execute()
    )

    all_outcomes = supabase.table("incident_outcomes").select("*").execute()
    outcome_map = {o["incident_id"]: o for o in (all_outcomes.data or [])}

    # Group by stage
    stage_data: dict = defaultdict(lambda: {
        "total": 0, "resolved": 0, "open": 0, "high": 0,
        "resolution_times": [], "action_categories": defaultdict(int),
        "incidents": []
    })

    for inc in (all_incidents.data or []):
        stage = inc["stage"]
        stage_data[stage]["total"] += 1
        stage_data[stage]["incidents"].append(inc)
        if inc["status"] == "resolved":
            stage_data[stage]["resolved"] += 1
            if inc.get("resolved_at") and inc.get("created_at"):
                created = datetime.fromisoformat(inc["created_at"].replace("Z", "+00:00"))
                resolved = datetime.fromisoformat(inc["resolved_at"].replace("Z", "+00:00"))
                mins = (resolved - created).total_seconds() / 60
                stage_data[stage]["resolution_times"].append(mins)
        else:
            stage_data[stage]["open"] += 1
        if inc["severity"] == "high":
            stage_data[stage]["high"] += 1
        outcome = outcome_map.get(inc["id"])
        if outcome:
            cat = outcome.get("action_category", "other")
            stage_data[stage]["action_categories"][cat] += 1

    results = []
    for stage, data in stage_data.items():
        if data["total"] < 2:
            continue

        resolution_rate = round(data["resolved"] / data["total"] * 100) if data["total"] > 0 else 0
        avg_resolution_time = round(sum(data["resolution_times"]) / len(data["resolution_times"])) if data["resolution_times"] else None

        # Recurrence detection: multiple incidents on same stage = recurring
        incidents_sorted = sorted(data["incidents"], key=lambda x: x["created_at"])
        recurrence_gaps = []
        for i in range(1, len(incidents_sorted)):
            t1 = datetime.fromisoformat(incidents_sorted[i-1]["created_at"].replace("Z", "+00:00"))
            t2 = datetime.fromisoformat(incidents_sorted[i]["created_at"].replace("Z", "+00:00"))
            gap_hours = (t2 - t1).total_seconds() / 3600
            recurrence_gaps.append(gap_hours)

        avg_gap_hours = sum(recurrence_gaps) / len(recurrence_gaps) if recurrence_gaps else None
        is_recurring = data["total"] >= 3

        # Effectiveness score: high total + short gaps + low resolution rate = bad
        if data["total"] >= 3 and avg_gap_hours and avg_gap_hours < 48:
            effectiveness = "poor"
            insight = f"{stage.replace('_', ' ').title()} has had {data['total']} incidents in 30 days with an avg gap of {round(avg_gap_hours, 1)}hrs — fixes are not holding. Root cause likely unresolved."
        elif resolution_rate >= 80 and data["total"] <= 3:
            effectiveness = "good"
            insight = f"{stage.replace('_', ' ').title()} is being resolved effectively — {resolution_rate}% resolution rate with {data['total']} total incidents."
        elif resolution_rate >= 60:
            effectiveness = "moderate"
            insight = f"{stage.replace('_', ' ').title()} has a {resolution_rate}% resolution rate but {data['open']} incidents still open."
        else:
            effectiveness = "poor"
            insight = f"{stage.replace('_', ' ').title()} has a low {resolution_rate}% resolution rate — {data['open']} incidents remain unresolved."

        most_common_action = None
        if data["action_categories"]:
            most_common_action = max(data["action_categories"], key=lambda k: data["action_categories"][k])

        results.append({
            "stage": stage,
            "total_incidents": data["total"],
            "resolved": data["resolved"],
            "open": data["open"],
            "high_severity": data["high"],
            "resolution_rate": resolution_rate,
            "avg_resolution_minutes": avg_resolution_time,
            "avg_gap_hours": round(avg_gap_hours, 1) if avg_gap_hours else None,
            "is_recurring": is_recurring,
            "effectiveness": effectiveness,
            "most_common_action": most_common_action,
            "insight": insight,
        })

    results.sort(key=lambda x: (x["effectiveness"] == "poor", x["total_incidents"]), reverse=True)
    return {"effectiveness": results, "industry": industry, "days_analyzed": 30}


# ─── Phase 4: Playbook Generation ────────────────────────────────────────────

@app.get("/intelligence/playbook/{stage}")
async def generate_playbook(stage: str, industry: str = "cruise"):
    """
    Generate a standard operating procedure for a stage
    based on past incidents, outcomes, and what worked.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()

    # Get all incidents for this stage
    incidents_resp = (
        supabase.table("incidents")
        .select("id, severity, description, status, created_at, resolved_at")
        .eq("industry", industry)
        .eq("stage", stage)
        .gte("created_at", cutoff)
        .execute()
    )

    if not incidents_resp.data:
        raise HTTPException(status_code=404, detail=f"No incidents found for stage '{stage}' in the last 30 days")

    incidents = incidents_resp.data

    # Get all outcomes for these incidents
    incident_ids = [i["id"] for i in incidents]
    outcomes_resp = supabase.table("incident_outcomes").select("*").in_("incident_id", incident_ids).execute()
    outcomes = outcomes_resp.data or []

    # Get AI analyses
    logs_resp = supabase.table("analysis_logs").select("ai_analysis, confidence_score, created_at").in_("incident_id", incident_ids).order("confidence_score", desc=True).limit(5).execute()
    top_analyses = logs_resp.data or []

    # Build context for Groq
    incident_summary = f"{len(incidents)} incidents in 30 days"
    resolved = [i for i in incidents if i["status"] == "resolved"]
    resolution_rate = round(len(resolved) / len(incidents) * 100) if incidents else 0

    actions_taken = [o["action_taken"] for o in outcomes if o.get("action_taken")]
    action_categories = defaultdict(int)
    for o in outcomes:
        if o.get("action_category"):
            action_categories[o["action_category"]] += 1

    improvements = [o for o in outcomes if o.get("health_after") and o.get("health_before") and o["health_after"] > o["health_before"]]
    best_actions = [o["action_taken"] for o in improvements[:3]] if improvements else []

    analyses_text = "\n".join(
        f"- (Confidence: {a.get('confidence_score', '?')}%) {a['ai_analysis'][:200]}..."
        for a in top_analyses[:3]
    ) if top_analyses else "No AI analyses available yet."

    prompt = (
        f"You are writing a Standard Operating Procedure (SOP) for a {industry} operations team.\n\n"
        f"Stage: {stage.replace('_', ' ').title()}\n"
        f"Data from last 30 days:\n"
        f"- {incident_summary} ({resolution_rate}% resolved)\n"
        f"- Actions taken: {', '.join(actions_taken[:5]) if actions_taken else 'Not recorded yet'}\n"
        f"- Most effective fixes: {', '.join(best_actions) if best_actions else 'Not enough outcome data yet'}\n"
        f"- Most common action category: {max(action_categories, key=lambda k: action_categories[k]) if action_categories else 'Unknown'}\n\n"
        f"Top AI analyses of past incidents:\n{analyses_text}\n\n"
        "Write a concise SOP with exactly these sections:\n"
        "**TRIGGER CONDITIONS** — when to activate this playbook\n"
        "**IMMEDIATE ACTIONS (0-5 min)** — what to do first\n"
        "**ESCALATION (5-15 min)** — if immediate actions don't work\n"
        "**ROOT CAUSE CHECKLIST** — common root causes to verify\n"
        "**PREVENTION** — how to reduce recurrence\n\n"
        "Keep each section to 2-3 bullet points. Be specific to this stage and industry."
    )

    playbook_text = await call_groq(prompt, max_tokens=800)

    return {
        "stage": stage,
        "industry": industry,
        "playbook": playbook_text,
        "data_summary": {
            "total_incidents": len(incidents),
            "resolution_rate": resolution_rate,
            "actions_recorded": len(outcomes),
            "best_actions": best_actions,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
    }


# ─── Phase 2 Intelligence ─────────────────────────────────────────────────────

@app.get("/intelligence/health-scores")
def get_health_scores(industry: str = "cruise"):
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    response = supabase.table("workflow_metrics").select("stage, health_score, recorded_at").eq("industry", industry).gte("recorded_at", cutoff).order("recorded_at", desc=True).execute()
    stage_readings: dict = defaultdict(list)
    for row in response.data:
        stage_readings[row["stage"]].append(row["health_score"])
    results = []
    for stage, scores in stage_readings.items():
        recent = scores[:3]
        current = recent[0] if recent else 0
        trend = "stable"
        if len(recent) >= 2:
            diff = recent[0] - recent[-1]
            trend = "degrading" if diff > 5 else "improving" if diff < -5 else "stable"
        status = "healthy" if current >= 80 else "warning" if current >= 60 else "critical" if current >= 40 else "severe"
        results.append({"stage": stage, "health_score": round(current, 1), "avg_24h": round(sum(recent)/len(recent), 1), "trend": trend, "status": status})
    results.sort(key=lambda x: x["health_score"])
    return {"health_scores": results, "industry": industry}


@app.get("/intelligence/recurring-patterns")
def get_recurring_patterns(industry: str = "cruise"):
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    thresholds = INDUSTRY_THRESHOLDS.get(industry, {"queue": 50, "processing": 300, "throughput": 10})
    response = supabase.table("workflow_metrics").select("stage, queue_size, processing_time_seconds, throughput, health_score, recorded_at").eq("industry", industry).gte("recorded_at", cutoff).execute()
    stage_breaches: dict = defaultdict(list)
    for row in response.data:
        if row["queue_size"] > thresholds["queue"] or row["processing_time_seconds"] > thresholds["processing"] or row["throughput"] < thresholds["throughput"]:
            ts = datetime.fromisoformat(row["recorded_at"].replace("Z", "+00:00"))
            stage_breaches[row["stage"]].append({"hour": ts.hour, "dow": int(ts.strftime("%w")), "health": row["health_score"]})
    patterns = []
    for stage, breaches in stage_breaches.items():
        if len(breaches) < 3:
            continue
        hour_counts: dict = defaultdict(int)
        dow_counts: dict = defaultdict(int)
        for b in breaches:
            hour_counts[b["hour"]] += 1
            dow_counts[b["dow"]] += 1
        peak_hour = max(hour_counts, key=lambda h: hour_counts[h])
        peak_dow = max(dow_counts, key=lambda d: dow_counts[d])
        peak_hour_pct = round(hour_counts[peak_hour] / len(breaches) * 100)
        peak_dow_pct = round(dow_counts[peak_dow] / len(breaches) * 100)
        hour_label = f"{'12' if peak_hour == 12 else peak_hour % 12 or 12}{'am' if peak_hour < 12 else 'pm'}"
        insight = f"{stage.replace('_', ' ').title()} breached thresholds {len(breaches)} times in 30 days"
        if peak_hour_pct >= 40:
            insight += f", most often around {hour_label} ({peak_hour_pct}%)"
        if peak_dow_pct >= 40:
            insight += f" on {DAY_NAMES[peak_dow]}s ({peak_dow_pct}%)"
        patterns.append({
            "stage": stage, "breach_count": len(breaches),
            "peak_hour_label": hour_label, "peak_hour_pct": peak_hour_pct,
            "peak_dow_label": DAY_NAMES[peak_dow], "peak_dow_pct": peak_dow_pct,
            "insight": insight, "severity": "high" if len(breaches) > 20 else "medium" if len(breaches) > 10 else "low",
        })
    patterns.sort(key=lambda x: x["breach_count"], reverse=True)
    return {"patterns": patterns, "industry": industry, "days_analyzed": 30}


@app.get("/intelligence/cascade-predictions")
def get_cascade_predictions(industry: str = "cruise"):
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    thresholds = INDUSTRY_THRESHOLDS.get(industry, {"queue": 50, "processing": 300, "throughput": 10})
    response = supabase.table("workflow_metrics").select("stage, queue_size, processing_time_seconds, throughput, health_score, recorded_at").eq("industry", industry).gte("recorded_at", cutoff).order("recorded_at").execute()
    stage_buckets: dict = defaultdict(dict)
    for row in response.data:
        ts = datetime.fromisoformat(row["recorded_at"].replace("Z", "+00:00"))
        bucket_key = ts.replace(minute=0, second=0, microsecond=0).isoformat()
        breached = row["queue_size"] > thresholds["queue"] or row["processing_time_seconds"] > thresholds["processing"] or row["throughput"] < thresholds["throughput"]
        stage_buckets[row["stage"]][bucket_key] = {"health": row["health_score"], "breached": breached}
    stages = list(stage_buckets.keys())
    predictions = []
    for source in stages:
        for target in stages:
            if source == target:
                continue
            source_data = stage_buckets[source]
            target_data = stage_buckets[target]
            cascade_count = 0
            source_breach_count = 0
            for bucket_key, reading in source_data.items():
                if not reading["breached"]:
                    continue
                source_breach_count += 1
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
            recent_source = sorted(source_data.keys())[-3:]
            source_currently_stressed = any(source_data[k]["breached"] for k in recent_source)
            predictions.append({
                "source_stage": source, "target_stage": target,
                "confidence": confidence, "cascade_count": cascade_count,
                "source_breach_count": source_breach_count, "lag_hours": 2,
                "source_currently_stressed": source_currently_stressed,
                "insight": f"When {source.replace('_', ' ').title()} breaches, {target.replace('_', ' ').title()} degrades 2hrs later {confidence}% of the time",
                "alert": source_currently_stressed and confidence >= 60,
            })
    predictions.sort(key=lambda x: (x["alert"], x["confidence"]), reverse=True)
    return {"predictions": predictions[:6], "industry": industry}


@app.get("/intelligence/anomaly-scores")
def get_anomaly_scores(industry: str = "cruise"):
    cutoff_30d = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    cutoff_24h = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    all_resp = supabase.table("workflow_metrics").select("stage, health_score, recorded_at").eq("industry", industry).gte("recorded_at", cutoff_30d).execute()
    stage_all: dict = defaultdict(list)
    stage_recent: dict = defaultdict(list)
    for row in all_resp.data:
        stage_all[row["stage"]].append(row["health_score"])
        if row["recorded_at"] >= cutoff_24h:
            stage_recent[row["stage"]].append(row["health_score"])
    scores = []
    for stage in stage_all:
        baseline_avg = sum(stage_all[stage]) / len(stage_all[stage])
        recent = stage_recent.get(stage, stage_all[stage][-3:])
        recent_avg = sum(recent) / len(recent)
        deviation = baseline_avg - recent_avg
        anomaly_score = round(min(100, max(0, (deviation / max(baseline_avg, 1)) * 100 * 2)), 1)
        scores.append({
            "stage": stage, "current_health": round(recent_avg, 1), "baseline_health": round(baseline_avg, 1),
            "deviation": round(deviation, 1), "anomaly_score": anomaly_score, "flag": anomaly_score > 30,
            "insight": f"{stage.replace('_', ' ').title()} is running {round(deviation, 1)} points below its 30-day average" if deviation > 5 else f"{stage.replace('_', ' ').title()} is performing normally",
        })
    scores.sort(key=lambda x: x["anomaly_score"], reverse=True)
    return {"anomaly_scores": scores, "industry": industry}


# ─── Phase 3 Intelligence ─────────────────────────────────────────────────────

@app.get("/intelligence/eta-to-breach")
def get_eta_to_breach(industry: str = "cruise"):
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=12)).isoformat()
    thresholds = INDUSTRY_THRESHOLDS.get(industry, {"queue": 50, "processing": 300, "throughput": 10})
    response = supabase.table("workflow_metrics").select("stage, health_score, queue_size, processing_time_seconds, throughput, recorded_at").eq("industry", industry).gte("recorded_at", cutoff).order("recorded_at", desc=True).execute()
    stage_readings: dict = defaultdict(list)
    for row in response.data:
        stage_readings[row["stage"]].append(row)
    predictions = []
    for stage, readings in stage_readings.items():
        if len(readings) < 3:
            continue
        recent = readings[:6]
        health_values = [r["health_score"] for r in recent]
        current_health = health_values[0]
        n = len(health_values)
        x = list(range(n))
        x_mean = sum(x) / n
        y_mean = sum(health_values) / n
        numerator = sum((x[i] - x_mean) * (health_values[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))
        slope = numerator / denominator if denominator != 0 else 0
        health_change_per_hour = slope / 2
        queue_values = [r["queue_size"] for r in recent]
        proc_values = [r["processing_time_seconds"] for r in recent]
        tp_values = [r["throughput"] for r in recent]
        already_breached = queue_values[0] > thresholds["queue"] or proc_values[0] > thresholds["processing"] or tp_values[0] < thresholds["throughput"]
        if already_breached:
            eta_hours, status, urgency = 0, "breached", "critical"
        elif health_change_per_hour >= 0 or current_health >= 85:
            continue
        else:
            hours_to_critical = (current_health - 40) / abs(health_change_per_hour)
            eta_hours = round(hours_to_critical, 1)
            urgency = "critical" if eta_hours <= 2 else "warning" if eta_hours <= 6 else "monitor" if eta_hours <= 12 else "low"
            status = "declining"
        if urgency == "low":
            continue
        queue_trend = (queue_values[0] - queue_values[-1]) / max(len(queue_values) - 1, 1)
        proc_trend = (proc_values[0] - proc_values[-1]) / max(len(proc_values) - 1, 1)
        tp_trend = (tp_values[0] - tp_values[-1]) / max(len(tp_values) - 1, 1)
        factors = []
        if queue_trend > 2: factors.append(f"queue growing +{round(queue_trend, 1)}/reading")
        if proc_trend > 10: factors.append(f"processing time +{round(proc_trend, 1)}s/reading")
        if tp_trend < -1: factors.append(f"throughput falling {round(tp_trend, 1)}/reading")
        insight = f"{stage.replace('_', ' ').title()} {'has already breached — immediate action required' if eta_hours == 0 else f'will hit critical threshold in ~{eta_hours}hrs'}"
        if factors and eta_hours != 0:
            insight += f" (driven by: {', '.join(factors)})"
        predictions.append({"stage": stage, "current_health": round(current_health, 1), "health_change_per_hour": round(health_change_per_hour, 2), "eta_hours": eta_hours, "status": status, "urgency": urgency, "factors": factors, "insight": insight})
    urgency_order = {"critical": 0, "warning": 1, "monitor": 2}
    predictions.sort(key=lambda x: (urgency_order.get(x["urgency"], 4), x.get("eta_hours") or 999))
    return {"predictions": predictions, "industry": industry}


@app.get("/intelligence/capacity-forecast")
def get_capacity_forecast(industry: str = "cruise"):
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    thresholds = INDUSTRY_THRESHOLDS.get(industry, {"queue": 50, "processing": 300, "throughput": 10})
    response = supabase.table("workflow_metrics").select("stage, queue_size, processing_time_seconds, throughput, health_score, recorded_at").eq("industry", industry).gte("recorded_at", cutoff).execute()
    bucket_labels = ["Midnight–6am", "6am–12pm", "12pm–6pm", "6pm–Midnight"]
    slot_data: dict = defaultdict(lambda: {"total": 0, "breaches": 0, "avg_health": []})
    for row in response.data:
        ts = datetime.fromisoformat(row["recorded_at"].replace("Z", "+00:00"))
        dow = int(ts.strftime("%w"))
        hour_bucket = ts.hour // 6
        key = (row["stage"], dow, hour_bucket)
        slot_data[key]["total"] += 1
        slot_data[key]["avg_health"].append(row["health_score"])
        breached = row["queue_size"] > thresholds["queue"] or row["processing_time_seconds"] > thresholds["processing"] or row["throughput"] < thresholds["throughput"]
        if breached:
            slot_data[key]["breaches"] += 1
    high_risk_slots = []
    for (stage, dow, hour_bucket), data in slot_data.items():
        if data["total"] < 3:
            continue
        breach_rate = data["breaches"] / data["total"]
        avg_health = sum(data["avg_health"]) / len(data["avg_health"])
        if breach_rate >= 0.35:
            high_risk_slots.append({"stage": stage, "dow": dow, "dow_label": DAY_NAMES[dow], "hour_bucket": hour_bucket, "hour_label": bucket_labels[hour_bucket], "breach_rate": round(breach_rate * 100), "avg_health": round(avg_health, 1), "risk": "high" if breach_rate >= 0.6 else "medium"})
    now = datetime.now(timezone.utc)
    upcoming_risks = []
    for days_ahead in range(1, 8):
        future_date = now + timedelta(days=days_ahead)
        future_dow = int(future_date.strftime("%w"))
        for slot in high_risk_slots:
            if slot["dow"] == future_dow:
                slot_copy = dict(slot)
                slot_copy["date"] = future_date.strftime("%A, %b %d")
                slot_copy["days_away"] = days_ahead
                slot_copy["forecast"] = f"{slot['stage'].replace('_', ' ').title()} on {future_date.strftime('%A')} {slot['hour_label']} has a {slot['breach_rate']}% historical breach rate"
                upcoming_risks.append(slot_copy)
    upcoming_risks.sort(key=lambda x: (x["days_away"], -x["breach_rate"]))
    return {"forecast": upcoming_risks[:8], "industry": industry, "days_ahead": 7}


@app.get("/intelligence/whatif-simulation")
async def whatif_simulation(industry: str = "cruise", stage: str = "", change: str = "add_staff", magnitude: int = 2):
    if not stage:
        raise HTTPException(status_code=400, detail="stage required")
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    response = supabase.table("workflow_metrics").select("queue_size, processing_time_seconds, throughput, health_score").eq("industry", industry).eq("stage", stage).gte("recorded_at", cutoff).order("recorded_at", desc=True).limit(5).execute()
    if not response.data:
        raise HTTPException(status_code=404, detail=f"No recent metrics for '{stage}'")
    readings = response.data
    current_queue = sum(r["queue_size"] for r in readings) / len(readings)
    current_proc = sum(r["processing_time_seconds"] for r in readings) / len(readings)
    current_throughput = sum(r["throughput"] for r in readings) / len(readings)
    current_health = sum(r["health_score"] for r in readings) / len(readings)
    thresholds = INDUSTRY_THRESHOLDS.get(industry, {"queue": 50, "processing": 300, "throughput": 10})
    change_descriptions = {"add_staff": f"Adding {magnitude} staff member(s)", "reduce_queue": f"Reducing queue by {magnitude * 10}%", "upgrade_equipment": f"Upgrading equipment ({magnitude * 15}% processing improvement)", "extend_hours": f"Extending hours by {magnitude}hr(s)"}
    if change == "add_staff":
        projected_throughput = current_throughput * (1 + magnitude * 0.2)
        projected_proc = current_proc * (1 - magnitude * 0.1)
        projected_queue = current_queue * (1 - magnitude * 0.15)
    elif change == "reduce_queue":
        projected_queue = current_queue * (1 - magnitude * 0.1)
        projected_throughput = current_throughput * (1 + magnitude * 0.05)
        projected_proc = current_proc
    elif change == "upgrade_equipment":
        projected_proc = current_proc * (1 - magnitude * 0.15)
        projected_throughput = current_throughput * (1 + magnitude * 0.1)
        projected_queue = current_queue * (1 - magnitude * 0.08)
    else:
        projected_queue = current_queue * (1 - magnitude * 0.12)
        projected_throughput = current_throughput * (1 + magnitude * 0.08)
        projected_proc = current_proc
    projected_queue = max(0, projected_queue)
    projected_proc = max(0, projected_proc)
    projected_throughput = max(0, projected_throughput)
    projected_health = max(0, min(100, 100 - (projected_queue / thresholds["queue"] * 40) - (projected_proc / thresholds["processing"] * 40) + (min(projected_throughput, thresholds["throughput"]) / thresholds["throughput"] * 20)))
    health_improvement = projected_health - current_health
    would_resolve_breach = projected_queue <= thresholds["queue"] and projected_proc <= thresholds["processing"] and projected_throughput >= thresholds["throughput"]
    prompt = (f"Ops analyst simulating change in {industry}.\nStage: {stage}\nChange: {change_descriptions.get(change)}\nBefore: Queue {round(current_queue,1)} | Processing {round(current_proc,1)}s | Throughput {round(current_throughput,1)}/hr | Health {round(current_health,1)}\nAfter: Queue {round(projected_queue,1)} | Processing {round(projected_proc,1)}s | Throughput {round(projected_throughput,1)}/hr | Health {round(projected_health,1)}\nHealth improvement: +{round(health_improvement,1)} | Resolves breach: {'Yes' if would_resolve_breach else 'No'}\nIn 3-4 sentences: is this sufficient, what else may be needed, any risks? Be specific.")
    ai_assessment = await call_groq(prompt)
    return {"stage": stage, "industry": industry, "change": change, "change_description": change_descriptions.get(change), "magnitude": magnitude, "current": {"queue": round(current_queue, 1), "processing_time": round(current_proc, 1), "throughput": round(current_throughput, 1), "health": round(current_health, 1)}, "projected": {"queue": round(projected_queue, 1), "processing_time": round(projected_proc, 1), "throughput": round(projected_throughput, 1), "health": round(projected_health, 1)}, "health_improvement": round(health_improvement, 1), "would_resolve_breach": would_resolve_breach, "ai_assessment": ai_assessment}


# ─── Webhook ──────────────────────────────────────────────────────────────────

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
        raise HTTPException(status_code=400, detail="No data provided")
    thresholds = INDUSTRY_THRESHOLDS.get(body.industry, {"queue": 50, "processing": 300, "throughput": 10})
    issues = []
    for r in rows:
        row_issues = []
        if r.queue_size > thresholds["queue"]: row_issues.append(f"queue backed up ({r.queue_size}, threshold: {thresholds['queue']})")
        if r.processing_time_seconds > thresholds["processing"]: row_issues.append(f"processing too high ({r.processing_time_seconds}s)")
        if r.throughput < thresholds["throughput"]: row_issues.append(f"throughput critically low ({r.throughput}/hr)")
        if row_issues:
            issues.append({"stage": r.stage, "issues": row_issues})
    rows_text = "\n".join(f"- {r.stage}: Queue {r.queue_size} | Processing {r.processing_time_seconds}s | Throughput {r.throughput}/hr" for r in rows)
    issues_text = "\n".join(f"- {i['stage']}: {', '.join(i['issues'])}" for i in issues) if issues else "No violations."
    prompt = f"Senior ops analyst. {body.industry}.\nWorkflow:\n{rows_text}\nViolations:\n{issues_text}\n1. Worst bottleneck with numbers\n2. Cascade impact\n3. 3 actions in 30 min. No generic advice."
    ai_analysis = await call_groq(prompt)
    return {"detected_issues": issues, "ai_analysis": ai_analysis}


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
        raise HTTPException(status_code=401, detail="Invalid secret")
    created = []
    for event in payload.events:
        industry = event.industry
        thresholds = INDUSTRY_THRESHOLDS.get(industry, {"queue": 50, "processing": 300, "throughput": 10})
        violations = []
        if event.queue_size > thresholds["queue"]: violations.append(f"Queue {event.queue_size} exceeds {thresholds['queue']}")
        if event.processing_time_seconds > thresholds["processing"]: violations.append(f"Processing {event.processing_time_seconds}s exceeds {thresholds['processing']}s")
        if event.throughput < thresholds["throughput"]: violations.append(f"Throughput {event.throughput}/hr below {thresholds['throughput']}/hr")
        health = max(0, min(100, 100 - (event.queue_size / thresholds["queue"] * 30) - (event.processing_time_seconds / thresholds["processing"] * 30) + (min(event.throughput, thresholds["throughput"]) / thresholds["throughput"] * 10)))
        supabase.table("workflow_metrics").insert({"industry": industry, "stage": event.stage, "queue_size": event.queue_size, "processing_time_seconds": event.processing_time_seconds, "throughput": event.throughput, "health_score": round(health, 1)}).execute()
        if violations:
            severity = "high" if len(violations) >= 2 else "medium"
            inc = supabase.table("incidents").insert({"stage": event.stage, "severity": severity, "description": ". ".join(violations), "status": "open", "industry": industry}).execute()
            if inc.data:
                created.append(inc.data[0])
    return {"received": len(payload.events), "incidents_created": len(created)}
