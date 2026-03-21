from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import List, Optional
import os
import httpx
from supabase import create_client
from datetime import datetime, timezone

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


# ─── Groq helper ────────────────────────────────────────────────────────────

async def call_groq(prompt: str) -> str:
    """Call Groq API and return the text response. Raises friendly errors."""
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
                detail="GROQ_RATE_LIMIT: The AI service is temporarily rate limited. Please wait 60 seconds and try again, or add your own Groq API key.",
            )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]


# ─── Email helper ────────────────────────────────────────────────────────────

async def send_alert_email(incident: dict):
    """Send a HIGH severity alert email via Resend."""
    if not RESEND_API_KEY or not ALERT_EMAIL:
        return  # Email not configured — skip silently
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


# ─── Routes ─────────────────────────────────────────────────────────────────

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
    """Return incident counts for today vs yesterday for trend indicators."""
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

    total = len(incidents)
    high = sum(1 for i in incidents if i.get("severity") == "high")
    open_count = sum(1 for i in incidents if i.get("status") == "open")

    return {
        "total": total,
        "high_severity": high,
        "open": open_count,
        "today_count": today_count,
        "yesterday_count": yesterday_count,
        "trend": today_count - yesterday_count,
    }


@app.patch("/incidents/{incident_id}/resolve")
def resolve_incident(incident_id: str):
    """Mark an incident as resolved."""
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
    """Return all saved AI analyses for an incident."""
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

    # Save to audit trail
    supabase.table("analysis_logs").insert({
        "incident_id": incident_id,
        "ai_analysis": analysis,
        "triggered_by": "user",
    }).execute()

    # Send email alert for HIGH severity
    if incident.get("severity") == "high":
        await send_alert_email(incident)

    return {
        "incident_id": incident_id,
        "stage": incident.get("stage"),
        "severity": incident.get("severity"),
        "ai_analysis": analysis,
    }


# ─── Custom analysis ─────────────────────────────────────────────────────────

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

    thresholds = INDUSTRY_THRESHOLDS.get(
        body.industry,
        {"queue": 50, "processing": 300, "throughput": 10}
    )

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
        f"Context: You are analyzing a {body.industry} workflow. Use industry-appropriate language and urgency. "
        "Reference actual metric values — no generic advice."
    )

    ai_analysis = await call_groq(prompt)
    return {"detected_issues": issues, "ai_analysis": ai_analysis}


# ─── Webhook endpoint ────────────────────────────────────────────────────────

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
    """
    Webhook endpoint — companies can POST their live operational data here.
    Automatically detects incidents and triggers AI analysis on critical ones.
    """
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

                # Auto-analyze HIGH severity incidents
                if severity == "high":
                    try:
                        prompt = (
                            f"You are a senior operations analyst. A HIGH severity incident was just auto-detected via webhook in a {industry} operation.\n\n"
                            f"Stage: {event.stage}\n"
                            f"Queue size: {event.queue_size} (threshold: {thresholds['queue']})\n"
                            f"Processing time: {event.processing_time_seconds}s (threshold: {thresholds['processing']}s)\n"
                            f"Throughput: {event.throughput}/hr (threshold: {thresholds['throughput']}/hr)\n"
                            f"Violations: {description}\n\n"
                            "Provide immediate root cause analysis and 3 urgent actions for the ops team. Be concise and direct."
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
                        pass  # Don't fail the webhook if AI analysis fails

    return {
        "received": len(payload.events),
        "incidents_created": len(created_incidents),
        "auto_analyzed": len(triggered_analyses),
        "incidents": created_incidents,
    }
