import asyncio
from fastapi import FastAPI, HTTPException, Request
from fastapi import UploadFile, File, Form
import jwt as pyjwt
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import List, Optional
import os
import re
import httpx
import io
import csv
import logging
from supabase import create_client
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from ops_agent import run_investigation
from services.live_data_service import fetch_live_incident_bundle, SUPPORTED_LIVE_INDUSTRIES, build_fallback_live_result
from services.metrics_service import (
    get_metrics_snapshot,
    increment_metric,
    record_industry_selection,
    record_visitor_session_end,
    record_visitor_session_start,
)

load_dotenv()

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper())

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
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")
logger = logging.getLogger(__name__)


@app.on_event("startup")
async def log_startup_configuration():
    logger.info(
        "Startup configuration loaded: supabase_url=%s groq_key=%s resend_key=%s jwt_secret=%s",
        bool(os.getenv("SUPABASE_URL")),
        bool(GROQ_API_KEY),
        bool(RESEND_API_KEY),
        bool(SUPABASE_JWT_SECRET),
    )

INDUSTRY_THRESHOLDS = {
    "cruise":        {"queue": 50,  "processing": 300, "throughput": 10},
    "healthcare":    {"queue": 20,  "processing": 3600, "throughput": 5},
    "banking":       {"queue": 100, "processing": 600, "throughput": 5},
    "ecommerce":     {"queue": 200, "processing": 180, "throughput": 50},
    "airport":       {"queue": 80,  "processing": 600,  "throughput": 8},
    "construction":  {"queue": 4,   "processing": 14400, "throughput": 2},
    "civil":         {"queue": 8,   "processing": 480, "throughput": 2},
    "architecture":  {"queue": 10,  "processing": 720, "throughput": 1},
    "energy":        {"queue": 20,  "processing": 300, "throughput": 5},
    "water":         {"queue": 15,  "processing": 600, "throughput": 3},
    "weather":       {"queue": 30,  "processing": 900, "throughput": 2},
    "traffic":       {"queue": 100, "processing": 120, "throughput": 30},
    "telecom":       {"queue": 200, "processing": 1800, "throughput": 10},
    "manufacturing": {"queue": 50,  "processing": 300, "throughput": 20},
    "retail":        {"queue": 30,  "processing": 600, "throughput": 15},
    "food":          {"queue": 20,  "processing": 900, "throughput": 10},
    "pharma":        {"queue": 10,  "processing": 3600, "throughput": 2},
    "government":    {"queue": 500, "processing": 86400, "throughput": 1},
    "realestate":    {"queue": 50,  "processing": 172800, "throughput": 1},
    "education":     {"queue": 500, "processing": 86400, "throughput": 5},
    "media":         {"queue": 1000,"processing": 3600, "throughput": 50},
}

DAY_NAMES = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]

ACTION_CATEGORIES = {
    "staff": "staffing", "hire": "staffing", "personnel": "staffing", "team": "staffing",
    "equip": "equipment", "machine": "equipment", "hardware": "equipment", "system": "equipment",
    "process": "process", "procedure": "process", "workflow": "process",
    "escalat": "escalation", "manag": "escalation", "supervis": "escalation",
}

INDUSTRY_AI_CONTEXT = {
    "construction": "A project-management-oriented construction workflow involving permits, inspections, subcontractor coordination, and handoff risk.",
}

CONSTRUCTION_STAGE_LABELS = {
    "permits_approvals": "Permits & Approvals",
    "site_prep": "Site Prep",
    "foundation": "Foundation",
    "framing": "Framing",
    "mep_rough_in": "MEP Rough-In",
    "inspection": "Inspection",
    "finishing": "Finishing",
    "handover": "Handover",
}

CONSTRUCTION_STAGE_RECOMMENDATIONS = {
    "permits_approvals": ["escalate permit review", "resequence non-blocked work", "confirm outstanding AHJ comments"],
    "site_prep": ["clear prerequisite approvals", "rebalance field crews", "validate access and mobilization constraints"],
    "foundation": ["verify concrete, rebar, and embed delivery dependencies", "shift labor to non-blocked prep", "lock inspection windows before pours"],
    "framing": ["rebalance subcontractor allocation", "release alternative workfaces", "confirm material and lift access before crew start"],
    "mep_rough_in": ["expedite MEP subcontractor recovery plan", "sequence other ready areas first", "validate long-lead material dependencies"],
    "inspection": ["expedite inspection scheduling", "package complete inspection-ready areas", "isolate failed scope before rework spreads"],
    "finishing": ["focus crews on turnover-critical spaces", "protect completed work from rework", "resequence punch-sensitive activities"],
    "handover": ["burn down punch-list backlog", "close documentation gaps", "protect owner walkthrough dates"],
}


def get_industry_ai_context(industry: str) -> str:
    return INDUSTRY_AI_CONTEXT.get(industry, f"A workflow-driven {industry} operation.")


def format_stage_label(stage: str, industry: str = "") -> str:
    if industry == "construction":
        return CONSTRUCTION_STAGE_LABELS.get(stage, stage.replace("_", " ").title())
    return stage.replace("_", " ").title()


def get_stage_specific_actions(industry: str, stage: str) -> str:
    if industry == "construction":
        actions = CONSTRUCTION_STAGE_RECOMMENDATIONS.get(stage, [
            "resequence non-blocked work",
            "rebalance subcontractor allocation",
            "validate predecessor dependencies",
        ])
        return ", ".join(actions)
    return "reduce the active bottleneck, protect downstream throughput, and confirm the next handoff"


def describe_metric_signal(industry: str, stage: str, queue_size: float, processing_time_seconds: float, throughput: float) -> str:
    if industry != "construction":
        return (
            f"Queue {queue_size} exceeds threshold. "
            f"Processing time {processing_time_seconds}s is elevated. "
            f"Throughput is {throughput}/hr."
        )

    stage_label = format_stage_label(stage, industry)
    if stage == "permits_approvals":
        return (
            f"{stage_label} backlog at {queue_size:.0f} submittals. Average approval cycle {processing_time_seconds / 3600:.1f} hours "
            f"with throughput at {throughput:.1f}/hr, creating mobilization risk for downstream work."
        )
    if stage == "inspection":
        return (
            f"{stage_label} queue at {queue_size:.0f} inspection requests. Average scheduling/review cycle {processing_time_seconds / 3600:.1f} hours "
            f"with only {throughput:.1f}/hr clearing, raising failed inspection rework and delay risk."
        )
    if stage == "framing":
        return (
            f"{stage_label} workfront has {queue_size:.0f} blocked tasks. Average cycle time is {processing_time_seconds / 3600:.1f} hours "
            f"and output is {throughput:.1f}/hr, increasing framing crew idle risk."
        )
    if stage == "mep_rough_in":
        return (
            f"{stage_label} has {queue_size:.0f} constrained areas waiting on subcontractor progress. Average cycle time is {processing_time_seconds / 3600:.1f} hours "
            f"with throughput at {throughput:.1f}/hr, putting inspections and finishes at risk."
        )
    if stage == "handover":
        return (
            f"{stage_label} is carrying {queue_size:.0f} open turnover items. Average closeout cycle is {processing_time_seconds / 3600:.1f} hours "
            f"with throughput at {throughput:.1f}/hr, signaling punch-list backlog risk."
        )
    return (
        f"{stage_label} is carrying {queue_size:.0f} blocked tasks. Average cycle time is {processing_time_seconds / 3600:.1f} hours "
        f"with throughput at {throughput:.1f}/hr, increasing downstream schedule slippage risk."
    )


# ─── Helpers ──────────────────────────────────────────────────────────────────

async def call_groq(prompt: str, max_tokens: int = 500) -> str:
    if not GROQ_API_KEY:
        logger.error("call_groq requested without GROQ_API_KEY configured")
        raise HTTPException(status_code=503, detail="AI provider is not configured on the backend. Set GROQ_API_KEY on Render.")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                json={"model": "llama-3.3-70b-versatile", "messages": [{"role": "user", "content": prompt}], "max_tokens": max_tokens},
            )
            if response.status_code == 429:
                raise HTTPException(status_code=429, detail="GROQ_RATE_LIMIT: Rate limited. Wait 60s.")
            if response.status_code in {401, 403}:
                logger.error("Groq authentication failed with status %s", response.status_code)
                raise HTTPException(status_code=503, detail="AI provider authentication failed. Verify GROQ_API_KEY on Render.")
            response.raise_for_status()
            payload = response.json()
            choices = payload.get("choices") or []
            if not choices:
                logger.error("Groq returned no choices: %s", payload)
                raise HTTPException(status_code=502, detail="AI provider returned an empty response.")
            return choices[0]["message"]["content"]
    except HTTPException:
        raise
    except httpx.TimeoutException:
        logger.exception("Groq request timed out")
        raise HTTPException(status_code=504, detail="AI provider timed out before completing the request.")
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code if exc.response else 502
        logger.exception("Groq HTTP error with status %s", status_code)
        raise HTTPException(status_code=502, detail=f"AI provider request failed with status {status_code}.")
    except Exception:
        logger.exception("Unexpected call_groq failure")
        raise HTTPException(status_code=500, detail="AI analysis failed on the backend.")


def extract_confidence(text: str) -> tuple[int, str]:
    explicit = re.search(r'(\d{1,3})\s*%\s*confiden', text, re.IGNORECASE)
    if explicit:
        score = min(100, max(0, int(explicit.group(1))))
        return score, f"Explicitly stated {score}% confidence"
    text_lower = text.lower()
    high_words = ["clearly", "definitely", "certainly", "obvious", "evident", "undoubtedly", "strongly indicates"]
    medium_words = ["likely", "probably", "suggests", "appears", "seems", "indicates"]
    low_words = ["possibly", "may", "might", "unclear", "uncertain", "could be"]
    high = sum(1 for w in high_words if w in text_lower)
    medium = sum(1 for w in medium_words if w in text_lower)
    low = sum(1 for w in low_words if w in text_lower)
    if high >= 2: return 88, "Analysis uses high-certainty language"
    elif high == 1 and low == 0: return 80, "Analysis shows strong directional confidence"
    elif medium >= 2 and low == 0: return 70, "Analysis uses moderately confident language"
    elif low >= 2: return 45, "Analysis expresses significant uncertainty"
    elif low == 1: return 60, "Analysis notes some uncertainty"
    else: return 72, "Analysis based on available incident data"


def categorize_action(action_text: str) -> str:
    text_lower = action_text.lower()
    for keyword, category in ACTION_CATEGORIES.items():
        if keyword in text_lower:
            return category
    return "other"


def is_elevated_severity(severity: str) -> bool:
    return severity in {"high", "critical"}


def upsert_live_incident_record(incident: dict) -> dict | None:
    stage = incident.get("affected_system") or incident.get("title", "live_signal").lower().replace(" ", "_")
    severity = incident.get("severity", "medium")
    description = (
        f"{incident.get('title')}. {incident.get('description')} "
        f"Impact: {incident.get('user_impact')} "
        f"Source: {incident.get('source_system')} ({incident.get('region')})."
    ).strip()
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=4)).isoformat()
    existing = supabase.table("incidents").select("id").eq("industry", incident.get("industry")).eq(
        "stage", stage
    ).eq("status", "open").gte("created_at", cutoff).limit(1).execute()

    if existing.data:
        supabase.table("incidents").update({
            "description": description,
            "severity": severity,
        }).eq("id", existing.data[0]["id"]).execute()
        refreshed = supabase.table("incidents").select("*").eq("id", existing.data[0]["id"]).single().execute()
        return refreshed.data

    created = supabase.table("incidents").insert({
        "stage": stage,
        "severity": severity,
        "description": description,
        "status": "open",
        "industry": incident.get("industry"),
        "user_id": None,
    }).execute()
    return created.data[0] if created.data else None


def clear_demo_incidents_for_live_industry(industry: str):
    supabase.table("incidents").delete().eq("industry", industry).is_("user_id", "null").execute()


def insert_live_metric_record(metric_event: dict):
    industry = metric_event["industry"]
    thresholds = INDUSTRY_THRESHOLDS.get(industry, {"queue": 50, "processing": 300, "throughput": 10})
    health = max(
        0,
        min(
            100,
            100
            - (metric_event["queue_size"] / thresholds["queue"] * 30)
            - (metric_event["processing_time_seconds"] / thresholds["processing"] * 30)
            + (min(metric_event["throughput"], thresholds["throughput"]) / thresholds["throughput"] * 10),
        ),
    )
    supabase.table("workflow_metrics").insert({
        "industry": industry,
        "stage": metric_event["stage"],
        "queue_size": metric_event["queue_size"],
        "processing_time_seconds": metric_event["processing_time_seconds"],
        "throughput": metric_event["throughput"],
        "health_score": round(health, 1),
    }).execute()
    return round(health, 1)


def safe_increment_platform_metric(metric_name: str):
    try:
        increment_metric(metric_name)
    except Exception:
        logger.exception("Failed to increment platform metric '%s'", metric_name)


def summarize_incident_for_copilot(incident: dict) -> str:
    return (
        f"- Incident {incident.get('id', '')[:8]} | stage={incident.get('stage')} | severity={incident.get('severity')} | "
        f"status={incident.get('status')} | detected={incident.get('created_at')} | description={incident.get('description')}"
    )


def get_recent_industry_metrics_summary(industry: str, limit: int = 6) -> list[str]:
    response = (
        supabase.table("workflow_metrics")
        .select("stage, queue_size, processing_time_seconds, throughput, health_score, recorded_at")
        .eq("industry", industry)
        .order("recorded_at", desc=True)
        .limit(limit)
        .execute()
    )
    summary = []
    seen_stages = set()
    for row in response.data or []:
        stage = row.get("stage")
        if not stage or stage in seen_stages:
            continue
        seen_stages.add(stage)
        summary.append(
            f"- {stage}: queue={row.get('queue_size')} processing={row.get('processing_time_seconds')}s "
            f"throughput={row.get('throughput')}/hr health={row.get('health_score')} recorded_at={row.get('recorded_at')}"
        )
    return summary


def get_latest_investigation_log(industry: str) -> Optional[str]:
    try:
        incidents_resp = (
            supabase.table("incidents")
            .select("id")
            .eq("industry", industry)
            .order("created_at", desc=True)
            .limit(25)
            .execute()
        )
        incident_ids = [row["id"] for row in (incidents_resp.data or []) if row.get("id")]
        query = (
            supabase.table("analysis_logs")
            .select("ai_analysis, created_at, incident_id, triggered_by")
            .eq("triggered_by", "agent_investigation")
            .order("created_at", desc=True)
            .limit(10)
        )
        if incident_ids:
            query = query.in_("incident_id", incident_ids)
        response = query.execute()
        if response.data:
            return response.data[0].get("ai_analysis")
    except Exception:
        logger.exception("Failed to load latest investigation log for industry=%s", industry)
    return None


def build_copilot_context(industry: str, message: str, incident_id: Optional[str] = None) -> tuple[str, list[str]]:
    thresholds = INDUSTRY_THRESHOLDS.get(industry, {"queue": 50, "processing": 300, "throughput": 10})
    sources = [f"thresholds:{industry}", f"industry:{industry}"]

    incidents_query = (
        supabase.table("incidents")
        .select("id, stage, severity, description, status, created_at")
        .eq("industry", industry)
        .order("created_at", desc=True)
        .limit(8)
    )
    incidents_resp = incidents_query.execute()
    incidents = incidents_resp.data or []

    selected_incident = None
    if incident_id:
        selected_resp = (
            supabase.table("incidents")
            .select("id, stage, severity, description, status, created_at")
            .eq("id", incident_id)
            .limit(1)
            .execute()
        )
        if selected_resp.data:
            selected_incident = selected_resp.data[0]
            sources.insert(0, f"incident:{selected_incident.get('stage')}")

    incident_summaries = [summarize_incident_for_copilot(incident) for incident in incidents]

    latest_analysis = None
    if incident_id:
        analysis_resp = (
            supabase.table("analysis_logs")
            .select("ai_analysis, confidence_score, created_at")
            .eq("incident_id", incident_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if analysis_resp.data:
            latest_analysis = analysis_resp.data[0]
            sources.append("analysis:latest")
    elif incidents:
        incident_ids = [incident["id"] for incident in incidents if incident.get("id")]
        if incident_ids:
            analysis_resp = (
                supabase.table("analysis_logs")
                .select("incident_id, ai_analysis, confidence_score, created_at")
                .in_("incident_id", incident_ids)
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            if analysis_resp.data:
                latest_analysis = analysis_resp.data[0]
                sources.append("analysis:latest")

    latest_investigation = get_latest_investigation_log(industry)
    if latest_investigation:
        sources.append("investigation:latest")

    metric_summary = get_recent_industry_metrics_summary(industry)
    if metric_summary:
        sources.append("metrics:recent")

    live_data_relevant = industry in SUPPORTED_LIVE_INDUSTRIES or "live" in message.lower()
    live_summary = ""
    if live_data_relevant:
        live_incidents = [incident for incident in incidents if incident.get("status") == "open"][:3]
        if live_incidents:
            live_summary = "\n".join(summarize_incident_for_copilot(incident) for incident in live_incidents)
            sources.append("live-data:current")

    platform_metrics_summary = ""
    if any(token in message.lower() for token in ["usage", "telemetry", "visitors", "sessions", "metrics", "trend"]):
        try:
            snapshot = get_metrics_snapshot()
            platform_metrics_summary = (
                f"- visitors_today={snapshot.get('visitors_today', 0)}\n"
                f"- active_sessions={snapshot.get('active_sessions', 0)}\n"
                f"- incidents_analyzed={snapshot.get('incidents_analyzed', 0)}\n"
                f"- agent_investigations={snapshot.get('agent_investigations', 0)}\n"
                f"- webhook_events_received={snapshot.get('webhook_events_received', 0)}\n"
                f"- live_data_refresh_calls={snapshot.get('live_data_refresh_calls', 0)}\n"
                f"- industries_explored={snapshot.get('industries_explored', 0)}"
            )
            sources.append("platform-metrics:current")
        except Exception:
            logger.exception("Failed to build platform metrics context for copilot")

    context = (
        f"Industry: {industry}\n"
        f"Industry context: {get_industry_ai_context(industry)}\n"
        f"Thresholds: queue>{thresholds['queue']} processing>{thresholds['processing']} throughput<{thresholds['throughput']}\n\n"
        f"Selected incident:\n{summarize_incident_for_copilot(selected_incident) if selected_incident else 'None selected.'}\n\n"
        f"Current incidents:\n{chr(10).join(incident_summaries) if incident_summaries else 'No current incidents.'}\n\n"
        f"Recent stage metrics:\n{chr(10).join(metric_summary) if metric_summary else 'No recent workflow metric data.'}\n\n"
        f"Latest incident analysis:\n{latest_analysis.get('ai_analysis') if latest_analysis else 'No prior analysis available.'}\n\n"
        f"Latest investigation output:\n{latest_investigation or 'No prior investigation available.'}\n\n"
        f"Current live-data snapshot:\n{live_summary or 'No live-data-specific context available.'}\n\n"
        f"Platform telemetry:\n{platform_metrics_summary or 'No platform telemetry requested or available.'}"
    )
    return context, list(dict.fromkeys(sources))


def format_live_data_response(industry: str, results: dict, all_incidents: list, mode_counts: dict):
    if industry == "all":
        overall_mode = "mixed" if len({r["data_mode"] for r in results.values()}) > 1 else next(iter(results.values()))["data_mode"] if results else "fallback"
        return {
            "success": True,
            "industry": "all",
            "data_mode": overall_mode,
            "incident_count": len(all_incidents),
            "incidents": all_incidents,
            "summary": {
                "supported_live_industries": list(SUPPORTED_LIVE_INDUSTRIES),
                "mode_counts": mode_counts,
                "industries": results,
            },
        }

    selected = results.get(industry, {
        "data_mode": "fallback",
        "incident_count": 0,
        "metric_count": 0,
        "stored_incident_count": 0,
        "source_systems": [],
        "source_system": None,
        "error": f"Industry '{industry}' is not supported for live data.",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "incidents": [],
    })
    return {
        "success": True,
        "industry": industry,
        "data_mode": selected["data_mode"],
        "incident_count": selected["incident_count"],
        "incidents": selected["incidents"],
        "summary": {
            "supported_live_industries": list(SUPPORTED_LIVE_INDUSTRIES),
            "industry_result": selected,
        },
    }


def build_route_level_fallback_response(industry: str, error: str):
    if industry == "all":
        results = {}
        all_incidents = []
        mode_counts = {"live": 0, "fallback": 0}
        for supported_industry in SUPPORTED_LIVE_INDUSTRIES:
            fallback_result = build_fallback_live_result(supported_industry, error)
            incidents = fallback_result["incidents"]
            results[supported_industry] = {
                "supported": fallback_result["supported"],
                "data_mode": fallback_result["data_mode"],
                "incident_count": len(incidents),
                "metric_count": len(fallback_result["metric_events"]),
                "stored_incident_count": 0,
                "source_systems": fallback_result.get("source_systems", []),
                "source_system": fallback_result.get("source_systems", [None])[0] if fallback_result.get("source_systems") else None,
                "error": fallback_result.get("error"),
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "incidents": incidents,
            }
            all_incidents.extend(incidents)
            mode_counts["fallback"] += 1
        return format_live_data_response("all", results, all_incidents, mode_counts)

    fallback_result = build_fallback_live_result(industry, error)
    incidents = fallback_result["incidents"]
    results = {
        industry: {
            "supported": fallback_result["supported"],
            "data_mode": fallback_result["data_mode"],
            "incident_count": len(incidents),
            "metric_count": len(fallback_result["metric_events"]),
            "stored_incident_count": 0,
            "source_systems": fallback_result.get("source_systems", []),
            "source_system": fallback_result.get("source_systems", [None])[0] if fallback_result.get("source_systems") else None,
            "error": fallback_result.get("error"),
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "incidents": incidents,
        }
    }
    return format_live_data_response(industry, results, incidents, {"live": 0, "fallback": 1})


async def send_alert_email(incident: dict):
    if not RESEND_API_KEY or not ALERT_EMAIL:
        return
    async with httpx.AsyncClient(timeout=10.0) as client:
        await client.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
            json={"from": "alerts@ops-intelligence.app", "to": [ALERT_EMAIL], "subject": f"🚨 HIGH Severity: {incident.get('stage')}", "html": f"<h2>High Severity Incident</h2><p><strong>Stage:</strong> {incident.get('stage')}</p><p><strong>Description:</strong> {incident.get('description')}</p>"},
        )


async def send_slack_alert(stage: str, severity: str, description: str, industry: str, health: float = None, eta_hours: float = None):
    if not SLACK_WEBHOOK_URL:
        return
    emoji = "🚨" if severity == "high" else "⚠️"
    health_str = f" | Health: {health}/100" if health else ""
    eta_str = f" | Breach in ~{eta_hours}hrs" if eta_hours else ""
    text = (
        f"{emoji} *{severity.upper()} — {stage.replace('_', ' ').title()}* ({industry})\n"
        f"{description}\n"
        f"{health_str}{eta_str}\n"
        f"<https://ops-intelligence-platform.vercel.app|View Dashboard →>"
    )
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(SLACK_WEBHOOK_URL, json={"text": text})
    except Exception:
        pass  # Never let Slack failure break the main flow


def get_user_id(request: Request) -> Optional[str]:
    """Extract user_id from Supabase JWT token if present. Returns None for unauthenticated."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header[7:]
    if not SUPABASE_JWT_SECRET:
        return None
    try:
        payload = pyjwt.decode(token, SUPABASE_JWT_SECRET, algorithms=["HS256"], options={"verify_aud": False})
        return payload.get("sub")
    except Exception:
        return None


# ─── Core routes ──────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "Ops Intelligence Platform"}


@app.get("/platform-metrics")
def get_platform_metrics():
    try:
        return get_metrics_snapshot()
    except Exception:
        logger.exception("Failed to load platform metrics snapshot")
        raise HTTPException(status_code=503, detail="Platform metrics are unavailable. Confirm workflow_metrics is reachable and backend env vars are set.")


@app.post("/platform-metrics/session-start")
def track_platform_session_start():
    try:
        return {"success": True, **record_visitor_session_start()}
    except Exception:
        logger.exception("Failed to record platform session start")
        raise HTTPException(status_code=503, detail="Platform metrics are unavailable. Confirm workflow_metrics is reachable and backend env vars are set.")


@app.post("/platform-metrics/session-end")
def track_platform_session_end():
    try:
        return {"success": True, "active_sessions": record_visitor_session_end()}
    except Exception:
        logger.exception("Failed to record platform session end")
        raise HTTPException(status_code=503, detail="Platform metrics are unavailable. Confirm workflow_metrics is reachable and backend env vars are set.")


@app.post("/platform-metrics/industry-selection")
def track_platform_industry_selection(industry: str = "cruise"):
    try:
        return {"success": True, **record_industry_selection(industry)}
    except Exception:
        logger.exception("Failed to record platform industry selection for %s", industry)
        raise HTTPException(status_code=503, detail="Platform metrics are unavailable. Confirm workflow_metrics is reachable and backend env vars are set.")


@app.get("/auth/me")
def get_me(request: Request):
    user_id = get_user_id(request)
    if not user_id:
        return {"authenticated": False, "user_id": None}
    # Get or create API key for this user
    existing = supabase.table("user_api_keys").select("api_key, label").eq("user_id", user_id).limit(1).execute()
    if existing.data:
        api_key = existing.data[0]["api_key"]
    else:
        result = supabase.table("user_api_keys").insert({"user_id": user_id, "label": "Default"}).execute()
        api_key = result.data[0]["api_key"] if result.data else None
    return {"authenticated": True, "user_id": user_id, "api_key": api_key}


@app.get("/incidents")
def get_incidents(request: Request, industry: str = "cruise"):
    user_id = get_user_id(request)
    if user_id:
        # Authenticated: show demo data (user_id is NULL) + their own data
        all_incidents = supabase.table("incidents").select("*").eq("industry", industry).is_("user_id", "null").order("created_at", desc=True).execute()
        user_incidents = supabase.table("incidents").select("*").eq("industry", industry).eq("user_id", user_id).order("created_at", desc=True).execute()
        combined = (user_incidents.data or []) + (all_incidents.data or [])
        combined.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return {"incidents": combined, "user_id": user_id}
    else:
        # Unauthenticated: show demo data only
        response = supabase.table("incidents").select("*").eq("industry", industry).is_("user_id", "null").order("created_at", desc=True).execute()
        return {"incidents": response.data, "user_id": None}


@app.get("/incidents/stats")
def get_stats(industry: str = "cruise"):
    all_resp = supabase.table("incidents").select("id, severity, status, created_at").eq("industry", industry).execute()
    incidents = all_resp.data or []
    now = datetime.now(timezone.utc)
    today_count = sum(1 for i in incidents if i.get("created_at") and (now - datetime.fromisoformat(i["created_at"].replace("Z", "+00:00"))).days < 1)
    yesterday_count = sum(1 for i in incidents if i.get("created_at") and 1 <= (now - datetime.fromisoformat(i["created_at"].replace("Z", "+00:00"))).days < 2)
    return {"total": len(incidents), "high_severity": sum(1 for i in incidents if is_elevated_severity(i.get("severity", ""))), "open": sum(1 for i in incidents if i.get("status") == "open"), "today_count": today_count, "yesterday_count": yesterday_count, "trend": today_count - yesterday_count}


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
    safe_increment_platform_metric("incidents_analyzed")
    logger.info("Analyze incident requested for incident_id=%s", incident_id)
    result = supabase.table("incidents").select("*").eq("id", incident_id).single().execute()
    if not result.data:
        logger.warning("Analyze incident could not find incident_id=%s", incident_id)
        raise HTTPException(status_code=404, detail="Incident not found")
    incident = result.data
    industry = incident.get("industry", "operations")

    # Fetch last 6 metric readings for richer AI context
    metrics_resp = supabase.table("workflow_metrics").select(
        "queue_size, processing_time_seconds, throughput, health_score, recorded_at"
    ).eq("industry", industry).eq("stage", incident.get("stage", "")).order(
        "recorded_at", desc=True
    ).limit(6).execute()

    metrics_context = ""
    if metrics_resp.data:
        readings = metrics_resp.data
        health_trend = " → ".join(str(r["health_score"]) for r in reversed(readings))
        latest = readings[0]
        thresholds = INDUSTRY_THRESHOLDS.get(industry, {"queue": 50, "processing": 300, "throughput": 10})
        metrics_context = (
            f"\nActual metrics (most recent first):"
            f"\n  Queue size: {latest['queue_size']} (threshold: {thresholds['queue']})"
            f"\n  Processing time: {latest['processing_time_seconds']}s (threshold: {thresholds['processing']}s)"
            f"\n  Throughput: {latest['throughput']}/hr (threshold: {thresholds['throughput']}/hr)"
            f"\n  Health trajectory: {health_trend}"
        )

    prompt = (
        f"Senior ops analyst.\n"
        f"Industry: {industry}.\n"
        f"Industry context: {get_industry_ai_context(industry)}\n"
        f"Stage: {incident.get('stage')} ({format_stage_label(incident.get('stage', ''), industry)}) | Severity: {incident.get('severity')}\n"
        f"Description: {incident.get('description')}"
        f"{metrics_context}\n\n"
        f"Using the actual numbers above:\n"
        f"1. Specific root cause (reference the exact metric values)\n"
        f"2. Downstream cascade impact on other stages\n"
        f"3. Three concrete actions in the next 30 minutes\n"
        f"Recommended action style for this stage: {get_stage_specific_actions(industry, incident.get('stage', ''))}\n"
        f"No generic advice. Use actual numbers."
    )
    logger.info("Analyze incident calling AI provider for incident_id=%s industry=%s stage=%s", incident_id, industry, incident.get("stage"))
    try:
        analysis = await call_groq(prompt)
    except HTTPException:
        logger.exception("Analyze incident AI provider failure for incident_id=%s", incident_id)
        raise
    except Exception:
        logger.exception("Analyze incident unexpected AI failure for incident_id=%s", incident_id)
        raise HTTPException(status_code=500, detail="Backend analysis failed")
    confidence_score, confidence_reason = extract_confidence(analysis)
    supabase.table("analysis_logs").insert({"incident_id": incident_id, "ai_analysis": analysis, "triggered_by": "user", "confidence_score": confidence_score, "confidence_reason": confidence_reason}).execute()
    if is_elevated_severity(incident.get("severity", "")):
        await send_alert_email(incident)
        latest_health = metrics_resp.data[0]["health_score"] if metrics_resp.data else None
        await send_slack_alert(
            stage=incident.get("stage", ""),
            severity=incident.get("severity", ""),
            description=incident.get("description", ""),
            industry=industry,
            health=latest_health,
        )
    logger.info("Analyze incident succeeded for incident_id=%s confidence=%s", incident_id, confidence_score)
    return {"success": True, "incident_id": incident_id, "stage": incident.get("stage"), "severity": incident.get("severity"), "ai_analysis": analysis, "confidence_score": confidence_score, "confidence_reason": confidence_reason}


# ─── Phase 4: Outcome Tracking ────────────────────────────────────────────────

class OutcomePayload(BaseModel):
    action_taken: str
    resolved_in_minutes: Optional[int] = None

@app.post("/incidents/{incident_id}/outcome")
async def log_outcome(incident_id: str, body: OutcomePayload):
    result = supabase.table("incidents").select("*").eq("id", incident_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Incident not found")
    incident = result.data
    industry = incident.get("industry", "operations")
    stage = incident.get("stage", "")
    incident_time = incident.get("created_at", datetime.now(timezone.utc).isoformat())
    before_resp = supabase.table("workflow_metrics").select("health_score").eq("industry", industry).eq("stage", stage).lte("recorded_at", incident_time).order("recorded_at", desc=True).limit(3).execute()
    health_before = sum(r["health_score"] for r in before_resp.data) / len(before_resp.data) if before_resp.data else None
    after_resp = supabase.table("workflow_metrics").select("health_score").eq("industry", industry).eq("stage", stage).order("recorded_at", desc=True).limit(3).execute()
    health_after = sum(r["health_score"] for r in after_resp.data) / len(after_resp.data) if after_resp.data else None
    action_category = categorize_action(body.action_taken)
    supabase.table("incident_outcomes").insert({"incident_id": incident_id, "action_taken": body.action_taken, "action_category": action_category, "health_before": round(health_before, 1) if health_before else None, "health_after": round(health_after, 1) if health_after else None, "resolved_in_minutes": body.resolved_in_minutes}).execute()
    improvement = round(health_after - health_before, 1) if health_before and health_after else None
    return {"success": True, "action_category": action_category, "health_before": round(health_before, 1) if health_before else None, "health_after": round(health_after, 1) if health_after else None, "improvement": improvement}


@app.get("/incidents/{incident_id}/outcome")
def get_outcome(incident_id: str):
    response = supabase.table("incident_outcomes").select("*").eq("incident_id", incident_id).order("created_at", desc=True).limit(1).execute()
    return {"outcome": response.data[0] if response.data else None}


# ─── Phase 4: Resolution Effectiveness ───────────────────────────────────────

@app.get("/intelligence/resolution-effectiveness")
def get_resolution_effectiveness(industry: str = "cruise"):
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    all_incidents = supabase.table("incidents").select("id, stage, severity, status, created_at, resolved_at").eq("industry", industry).gte("created_at", cutoff).order("created_at").execute()
    all_outcomes = supabase.table("incident_outcomes").select("*").execute()
    outcome_map = {o["incident_id"]: o for o in (all_outcomes.data or [])}
    stage_data: dict = defaultdict(lambda: {"total": 0, "resolved": 0, "open": 0, "high": 0, "resolution_times": [], "action_categories": defaultdict(int), "incidents": []})
    for inc in (all_incidents.data or []):
        stage = inc["stage"]
        stage_data[stage]["total"] += 1
        stage_data[stage]["incidents"].append(inc)
        if inc["status"] == "resolved":
            stage_data[stage]["resolved"] += 1
            if inc.get("resolved_at") and inc.get("created_at"):
                created = datetime.fromisoformat(inc["created_at"].replace("Z", "+00:00"))
                resolved = datetime.fromisoformat(inc["resolved_at"].replace("Z", "+00:00"))
                stage_data[stage]["resolution_times"].append((resolved - created).total_seconds() / 60)
        else:
            stage_data[stage]["open"] += 1
        if is_elevated_severity(inc["severity"]):
            stage_data[stage]["high"] += 1
        outcome = outcome_map.get(inc["id"])
        if outcome:
            stage_data[stage]["action_categories"][outcome.get("action_category", "other")] += 1
    results = []
    for stage, data in stage_data.items():
        if data["total"] < 2:
            continue
        resolution_rate = round(data["resolved"] / data["total"] * 100) if data["total"] > 0 else 0
        avg_resolution_time = round(sum(data["resolution_times"]) / len(data["resolution_times"])) if data["resolution_times"] else None
        incidents_sorted = sorted(data["incidents"], key=lambda x: x["created_at"])
        recurrence_gaps = []
        for i in range(1, len(incidents_sorted)):
            t1 = datetime.fromisoformat(incidents_sorted[i-1]["created_at"].replace("Z", "+00:00"))
            t2 = datetime.fromisoformat(incidents_sorted[i]["created_at"].replace("Z", "+00:00"))
            recurrence_gaps.append((t2 - t1).total_seconds() / 3600)
        avg_gap_hours = sum(recurrence_gaps) / len(recurrence_gaps) if recurrence_gaps else None
        is_recurring = data["total"] >= 3
        if data["total"] >= 3 and avg_gap_hours and avg_gap_hours < 48:
            effectiveness = "poor"
            insight = f"{stage.replace('_', ' ').title()} has had {data['total']} incidents in 30 days (avg gap: {round(avg_gap_hours, 1)}hrs) — fixes are not holding."
        elif resolution_rate >= 80 and data["total"] <= 3:
            effectiveness = "good"
            insight = f"{stage.replace('_', ' ').title()} is being resolved effectively — {resolution_rate}% resolution rate."
        elif resolution_rate >= 60:
            effectiveness = "moderate"
            insight = f"{stage.replace('_', ' ').title()} has a {resolution_rate}% resolution rate but {data['open']} incidents still open."
        else:
            effectiveness = "poor"
            insight = f"{stage.replace('_', ' ').title()} has a low {resolution_rate}% resolution rate — {data['open']} unresolved."
        most_common_action = max(data["action_categories"], key=lambda k: data["action_categories"][k]) if data["action_categories"] else None
        results.append({"stage": stage, "total_incidents": data["total"], "resolved": data["resolved"], "open": data["open"], "high_severity": data["high"], "resolution_rate": resolution_rate, "avg_resolution_minutes": avg_resolution_time, "avg_gap_hours": round(avg_gap_hours, 1) if avg_gap_hours else None, "is_recurring": is_recurring, "effectiveness": effectiveness, "most_common_action": most_common_action, "insight": insight})
    results.sort(key=lambda x: (x["effectiveness"] == "poor", x["total_incidents"]), reverse=True)
    return {"effectiveness": results, "industry": industry, "days_analyzed": 30}


# ─── Phase 4: Playbook ────────────────────────────────────────────────────────

@app.get("/intelligence/playbook/{stage}")
async def generate_playbook(stage: str, industry: str = "cruise"):
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    incidents_resp = supabase.table("incidents").select("id, severity, description, status, created_at, resolved_at").eq("industry", industry).eq("stage", stage).gte("created_at", cutoff).execute()
    if not incidents_resp.data:
        raise HTTPException(status_code=404, detail=f"No incidents found for stage '{stage}' in the last 30 days")
    incidents = incidents_resp.data
    incident_ids = [i["id"] for i in incidents]
    outcomes_resp = supabase.table("incident_outcomes").select("*").in_("incident_id", incident_ids).execute()
    outcomes = outcomes_resp.data or []
    logs_resp = supabase.table("analysis_logs").select("ai_analysis, confidence_score, created_at").in_("incident_id", incident_ids).order("confidence_score", desc=True).limit(5).execute()
    top_analyses = logs_resp.data or []
    resolved = [i for i in incidents if i["status"] == "resolved"]
    resolution_rate = round(len(resolved) / len(incidents) * 100) if incidents else 0
    actions_taken = [o["action_taken"] for o in outcomes if o.get("action_taken")]
    action_categories: dict = defaultdict(int)
    for o in outcomes:
        if o.get("action_category"):
            action_categories[o["action_category"]] += 1
    improvements = [o for o in outcomes if o.get("health_after") and o.get("health_before") and o["health_after"] > o["health_before"]]
    best_actions = [o["action_taken"] for o in improvements[:3]] if improvements else []
    analyses_text = "\n".join(f"- ({a.get('confidence_score', '?')}% conf) {a['ai_analysis'][:200]}..." for a in top_analyses[:3]) if top_analyses else "No analyses yet."
    prompt = (
        f"Write a Standard Operating Procedure for the {industry} operations team.\n"
        f"Industry context: {get_industry_ai_context(industry)}\n"
        f"Stage: {format_stage_label(stage, industry)}\n"
        f"{len(incidents)} incidents in 30 days ({resolution_rate}% resolved)\n"
        f"Best fixes: {', '.join(best_actions) if best_actions else 'Not recorded yet'}\n"
        f"Preferred action themes: {get_stage_specific_actions(industry, stage)}\n"
        f"Top analyses:\n{analyses_text}\n\n"
        "Write with these exact sections:\n**TRIGGER CONDITIONS**\n**IMMEDIATE ACTIONS (0-5 min)**\n**ESCALATION (5-15 min)**\n**ROOT CAUSE CHECKLIST**\n**PREVENTION**\n2-3 bullets each. Specific to this stage and industry."
    )
    playbook_text = await call_groq(prompt, max_tokens=800)
    return {"stage": stage, "industry": industry, "playbook": playbook_text, "data_summary": {"total_incidents": len(incidents), "resolution_rate": resolution_rate, "actions_recorded": len(outcomes), "best_actions": best_actions, "generated_at": datetime.now(timezone.utc).isoformat()}}


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
        insight = f"{stage.replace('_', ' ').title()} breached {len(breaches)} times in 30 days"
        if peak_hour_pct >= 40: insight += f", most often around {hour_label} ({peak_hour_pct}%)"
        if peak_dow_pct >= 40: insight += f" on {DAY_NAMES[peak_dow]}s ({peak_dow_pct}%)"
        patterns.append({"stage": stage, "breach_count": len(breaches), "peak_hour_label": hour_label, "peak_hour_pct": peak_hour_pct, "peak_dow_label": DAY_NAMES[peak_dow], "peak_dow_pct": peak_dow_pct, "insight": insight, "severity": "high" if len(breaches) > 20 else "medium" if len(breaches) > 10 else "low"})
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
            if source == target: continue
            source_data = stage_buckets[source]
            target_data = stage_buckets[target]
            cascade_count = 0
            source_breach_count = 0
            for bucket_key, reading in source_data.items():
                if not reading["breached"]: continue
                source_breach_count += 1
                ts = datetime.fromisoformat(bucket_key)
                future_ts = (ts + timedelta(hours=2)).isoformat()
                future_reading = target_data.get(future_ts)
                if future_reading and future_reading["breached"]: cascade_count += 1
            if source_breach_count < 5: continue
            confidence = round(cascade_count / source_breach_count * 100)
            if confidence < 40: continue
            recent_source = sorted(source_data.keys())[-3:]
            source_currently_stressed = any(source_data[k]["breached"] for k in recent_source)
            predictions.append({"source_stage": source, "target_stage": target, "confidence": confidence, "cascade_count": cascade_count, "source_breach_count": source_breach_count, "lag_hours": 2, "source_currently_stressed": source_currently_stressed, "insight": f"When {source.replace('_', ' ').title()} breaches, {target.replace('_', ' ').title()} degrades 2hrs later {confidence}% of the time", "alert": source_currently_stressed and confidence >= 60})
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
        if row["recorded_at"] >= cutoff_24h: stage_recent[row["stage"]].append(row["health_score"])
    scores = []
    for stage in stage_all:
        baseline_avg = sum(stage_all[stage]) / len(stage_all[stage])
        recent = stage_recent.get(stage, stage_all[stage][-3:])
        recent_avg = sum(recent) / len(recent)
        deviation = baseline_avg - recent_avg
        anomaly_score = round(min(100, max(0, (deviation / max(baseline_avg, 1)) * 100 * 2)), 1)
        scores.append({"stage": stage, "current_health": round(recent_avg, 1), "baseline_health": round(baseline_avg, 1), "deviation": round(deviation, 1), "anomaly_score": anomaly_score, "flag": anomaly_score > 30, "insight": f"{stage.replace('_', ' ').title()} is running {round(deviation, 1)} points below its 30-day average" if deviation > 5 else f"{stage.replace('_', ' ').title()} is performing normally"})
    scores.sort(key=lambda x: x["anomaly_score"], reverse=True)
    return {"anomaly_scores": scores, "industry": industry}


# ─── Phase 3 Intelligence ─────────────────────────────────────────────────────

@app.get("/intelligence/eta-to-breach")
def get_eta_to_breach(industry: str = "cruise"):
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=12)).isoformat()
    thresholds = INDUSTRY_THRESHOLDS.get(industry, {"queue": 50, "processing": 300, "throughput": 10})
    response = supabase.table("workflow_metrics").select("stage, health_score, queue_size, processing_time_seconds, throughput, recorded_at").eq("industry", industry).gte("recorded_at", cutoff).order("recorded_at", desc=True).execute()
    stage_readings: dict = defaultdict(list)
    for row in response.data: stage_readings[row["stage"]].append(row)
    predictions = []
    for stage, readings in stage_readings.items():
        if len(readings) < 3: continue
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
        already_breached = readings[0]["queue_size"] > thresholds["queue"] or readings[0]["processing_time_seconds"] > thresholds["processing"] or readings[0]["throughput"] < thresholds["throughput"]
        if already_breached:
            eta_hours, status, urgency = 0, "breached", "critical"
        elif health_change_per_hour >= 0 or current_health >= 85:
            continue
        else:
            hours_to_critical = (current_health - 40) / abs(health_change_per_hour)
            eta_hours = round(hours_to_critical, 1)
            urgency = "critical" if eta_hours <= 2 else "warning" if eta_hours <= 6 else "monitor" if eta_hours <= 12 else "low"
            status = "declining"
        if urgency == "low": continue
        queue_values = [r["queue_size"] for r in recent]
        proc_values = [r["processing_time_seconds"] for r in recent]
        tp_values = [r["throughput"] for r in recent]
        queue_trend = (queue_values[0] - queue_values[-1]) / max(len(queue_values) - 1, 1)
        proc_trend = (proc_values[0] - proc_values[-1]) / max(len(proc_values) - 1, 1)
        tp_trend = (tp_values[0] - tp_values[-1]) / max(len(tp_values) - 1, 1)
        factors = []
        if queue_trend > 2: factors.append(f"queue growing +{round(queue_trend, 1)}/reading")
        if proc_trend > 10: factors.append(f"processing time +{round(proc_trend, 1)}s/reading")
        if tp_trend < -1: factors.append(f"throughput falling {round(tp_trend, 1)}/reading")
        insight = f"{stage.replace('_', ' ').title()} {'has already breached — immediate action required' if eta_hours == 0 else f'will hit critical threshold in ~{eta_hours}hrs'}"
        if factors and eta_hours != 0: insight += f" (driven by: {', '.join(factors)})"
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
        if breached: slot_data[key]["breaches"] += 1
    high_risk_slots = []
    for (stage, dow, hour_bucket), data in slot_data.items():
        if data["total"] < 3: continue
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
    if not stage: raise HTTPException(status_code=400, detail="stage required")
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    response = supabase.table("workflow_metrics").select("queue_size, processing_time_seconds, throughput, health_score").eq("industry", industry).eq("stage", stage).gte("recorded_at", cutoff).order("recorded_at", desc=True).limit(5).execute()
    if not response.data: raise HTTPException(status_code=404, detail=f"No recent metrics for '{stage}'")
    readings = response.data
    current_queue = sum(r["queue_size"] for r in readings) / len(readings)
    current_proc = sum(r["processing_time_seconds"] for r in readings) / len(readings)
    current_throughput = sum(r["throughput"] for r in readings) / len(readings)
    current_health = sum(r["health_score"] for r in readings) / len(readings)
    thresholds = INDUSTRY_THRESHOLDS.get(industry, {"queue": 50, "processing": 300, "throughput": 10})
    change_descriptions = {"add_staff": f"Adding {magnitude} staff member(s)", "reduce_queue": f"Reducing queue by {magnitude * 10}%", "upgrade_equipment": f"Upgrading equipment ({magnitude * 15}% improvement)", "extend_hours": f"Extending hours by {magnitude}hr(s)"}
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
    prompt = (
        f"Ops analyst simulating {change_descriptions.get(change)} in {industry}.\n"
        f"Industry context: {get_industry_ai_context(industry)}\n"
        f"Stage: {stage} ({format_stage_label(stage, industry)})\n"
        f"Before: Queue {round(current_queue,1)} | Proc {round(current_proc,1)}s | Throughput {round(current_throughput,1)}/hr | Health {round(current_health,1)}\n"
        f"After: Queue {round(projected_queue,1)} | Proc {round(projected_proc,1)}s | Throughput {round(projected_throughput,1)}/hr | Health {round(projected_health,1)}\n"
        f"Health improvement: +{round(health_improvement,1)} | Resolves breach: {'Yes' if would_resolve_breach else 'No'}\n"
        f"Recommended action style for this stage: {get_stage_specific_actions(industry, stage)}\n"
        "In 3-4 sentences: is this sufficient, what else may be needed, any risks?"
    )
    ai_assessment = await call_groq(prompt)
    return {"stage": stage, "industry": industry, "change": change, "change_description": change_descriptions.get(change), "magnitude": magnitude, "current": {"queue": round(current_queue, 1), "processing_time": round(current_proc, 1), "throughput": round(current_throughput, 1), "health": round(current_health, 1)}, "projected": {"queue": round(projected_queue, 1), "processing_time": round(projected_proc, 1), "throughput": round(projected_throughput, 1), "health": round(projected_health, 1)}, "health_improvement": round(health_improvement, 1), "would_resolve_breach": would_resolve_breach, "ai_assessment": ai_assessment}


# ─── AI Agent endpoints ───────────────────────────────────────────────────────

class AgentInvestigateRequest(BaseModel):
    industry: str = "cruise"
    goal: Optional[str] = None


class CopilotChatRequest(BaseModel):
    message: str
    industry: str = "cruise"
    incident_id: Optional[str] = None
    role: Optional[str] = "ops"
    session_id: Optional[str] = None


class AgentDecisionRequest(BaseModel):
    decision_id: str
    approved: bool
    investigation_output: str
    industry: str = "cruise"
    stage: Optional[str] = None


@app.post("/agent/investigate")
async def agent_investigate(body: AgentInvestigateRequest):
    safe_increment_platform_metric("agent_investigations")
    industry = body.industry
    logger.info("Agent investigation requested for industry=%s goal_provided=%s", industry, bool(body.goal))
    helper_failure_result = None

    try:
        def run_agent_job():
            thread_supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
            return run_investigation(
                thread_supabase,
                GROQ_API_KEY,
                industry,
                body.goal or "",
            )

        result = await asyncio.to_thread(
            run_agent_job,
        )
    except Exception:
        logger.exception("Unexpected agent route failure for industry=%s", industry)
        helper_failure_result = {
            "success": False,
            "error": "Backend investigation failed",
            "reason": "backend",
            "industry": industry,
            "steps": [],
            "output": "",
            "decision_points": [],
            "investigated_at": datetime.now(timezone.utc).isoformat(),
        }

    if helper_failure_result is None and result.get("success", False):
        logger.info("Agent investigation succeeded for industry=%s steps=%s", industry, len(result.get("steps", [])))
        return result

    if helper_failure_result is None and not result.get("success", False):
        logger.warning(
            "Agent investigation returned failure for industry=%s reason=%s error=%s",
            industry,
            result.get("reason"),
            result.get("error"),
        )
        if result.get("reason") != "backend":
            return result
        helper_failure_result = result

    logger.warning(
        "Falling back to legacy inline investigation path for industry=%s after helper failure error=%s",
        industry,
        helper_failure_result.get("error") if helper_failure_result else "unknown",
    )

    """Run agent investigation with inline execution — no module import to avoid cache issues."""
    import json as _json

    industry = body.industry
    goal = body.goal or f"Investigate the {industry} operation. Check health scores, open incidents, cascade risks, ETAs, and patterns for any critical stages. Provide a prioritized action plan."

    AGENT_TOOLS = [
        {"type": "function", "function": {"name": "check_health_scores", "description": "Check current health scores for all stages. Always call this first.", "parameters": {"type": "object", "properties": {}, "required": []}}},
        {"type": "function", "function": {"name": "get_open_incidents", "description": "Get all currently open incidents.", "parameters": {"type": "object", "properties": {}, "required": []}}},
        {"type": "function", "function": {"name": "get_cascade_predictions", "description": "Check for active cascade risks between stages.", "parameters": {"type": "object", "properties": {}, "required": []}}},
        {"type": "function", "function": {"name": "get_eta_to_breach", "description": "Get ETA to breach for all declining stages.", "parameters": {"type": "object", "properties": {}, "required": []}}},
        {"type": "function", "function": {"name": "get_recurring_patterns", "description": "Get recurring failure patterns for a specific stage.", "parameters": {"type": "object", "properties": {"stage_name": {"type": "string", "description": "The exact stage name e.g. security_check"}}, "required": ["stage_name"]}}},
    ]

    def _execute_tool(tool_name: str, tool_args: dict) -> str:
        thresholds = INDUSTRY_THRESHOLDS.get(industry, {"queue": 50, "processing": 300, "throughput": 10})
        try:
            if tool_name == "check_health_scores":
                cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
                resp = supabase.table("workflow_metrics").select("stage, health_score, recorded_at").eq("industry", industry).gte("recorded_at", cutoff).order("recorded_at", desc=True).execute()
                stage_readings: dict = defaultdict(list)
                for row in (resp.data or []):
                    stage_readings[row["stage"]].append(row["health_score"])
                if not stage_readings:
                    return "No health data available."
                results = []
                for stage, scores in stage_readings.items():
                    recent = scores[:3]
                    current = recent[0]
                    trend = "stable"
                    if len(recent) >= 2:
                        diff = recent[0] - recent[-1]
                        trend = "degrading" if diff > 5 else "improving" if diff < -5 else "stable"
                    status = "healthy" if current >= 80 else "warning" if current >= 60 else "critical" if current >= 40 else "severe"
                    results.append(f"- {stage}: health={current}, trend={trend}, status={status}")
                return "Health scores:\n" + "\n".join(results)

            elif tool_name == "get_open_incidents":
                resp = supabase.table("incidents").select("id, stage, severity, description").eq("industry", industry).eq("status", "open").order("created_at", desc=True).execute()
                if not resp.data:
                    return "No open incidents."
                results = [f"- [{i['severity'].upper()}] {i['stage']}: {i['description']} (id: {i['id'][:8]}...)" for i in resp.data]
                return f"Open incidents ({len(resp.data)}):\n" + "\n".join(results)

            elif tool_name == "get_cascade_predictions":
                cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
                resp = supabase.table("workflow_metrics").select("stage, queue_size, processing_time_seconds, throughput, health_score, recorded_at").eq("industry", industry).gte("recorded_at", cutoff).order("recorded_at").execute()
                stage_buckets: dict = defaultdict(dict)
                for row in (resp.data or []):
                    ts = datetime.fromisoformat(row["recorded_at"].replace("Z", "+00:00"))
                    bk = ts.replace(minute=0, second=0, microsecond=0).isoformat()
                    breached = row["queue_size"] > thresholds["queue"] or row["processing_time_seconds"] > thresholds["processing"] or row["throughput"] < thresholds["throughput"]
                    stage_buckets[row["stage"]][bk] = {"health": row["health_score"], "breached": breached}
                stages = list(stage_buckets.keys())
                active_risks = []
                for source in stages:
                    for target in stages:
                        if source == target:
                            continue
                        sd = stage_buckets[source]
                        td = stage_buckets[target]
                        cc = 0
                        sbc = 0
                        for bk, reading in sd.items():
                            if not reading["breached"]:
                                continue
                            sbc += 1
                            ts2 = datetime.fromisoformat(bk)
                            ftk = (ts2 + timedelta(hours=2)).isoformat()
                            fr = td.get(ftk)
                            if fr and fr["breached"]:
                                cc += 1
                        if sbc < 5:
                            continue
                        conf = round(cc / sbc * 100)
                        if conf < 40:
                            continue
                        recent_src = sorted(sd.keys())[-3:]
                        stressed = any(sd[k]["breached"] for k in recent_src)
                        if stressed and conf >= 60:
                            active_risks.append(f"ACTIVE RISK: {source} -> {target} ({conf}% confidence)")
                return "Cascade risks:\n" + "\n".join(active_risks) if active_risks else "No active cascade risks."

            elif tool_name == "get_eta_to_breach":
                cutoff = (datetime.now(timezone.utc) - timedelta(hours=12)).isoformat()
                resp = supabase.table("workflow_metrics").select("stage, health_score, queue_size, processing_time_seconds, throughput, recorded_at").eq("industry", industry).gte("recorded_at", cutoff).order("recorded_at", desc=True).execute()
                sr: dict = defaultdict(list)
                for row in (resp.data or []):
                    sr[row["stage"]].append(row)
                results = []
                for stage, readings in sr.items():
                    if len(readings) < 3:
                        continue
                    recent = readings[:6]
                    hv = [r["health_score"] for r in recent]
                    ch = hv[0]
                    n = len(hv)
                    x = list(range(n))
                    xm = sum(x) / n
                    ym = sum(hv) / n
                    num = sum((x[i] - xm) * (hv[i] - ym) for i in range(n))
                    den = sum((x[i] - xm) ** 2 for i in range(n))
                    slope = num / den if den != 0 else 0
                    hcph = slope / 2
                    already = readings[0]["queue_size"] > thresholds["queue"] or readings[0]["processing_time_seconds"] > thresholds["processing"] or readings[0]["throughput"] < thresholds["throughput"]
                    if already:
                        results.append(f"- {stage}: ALREADY BREACHED")
                    elif hcph < 0 and ch < 85:
                        hrs = round((ch - 40) / abs(hcph), 1)
                        urg = "CRITICAL" if hrs <= 2 else "WARNING" if hrs <= 6 else "MONITOR"
                        results.append(f"- {stage}: {urg} breach in ~{hrs}hrs (health: {ch})")
                return "ETA to breach:\n" + "\n".join(results) if results else "All stages stable."

            elif tool_name == "get_recurring_patterns":
                sn = tool_args.get("stage_name", "")
                if not sn:
                    return "Provide a stage_name."
                cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
                resp = supabase.table("workflow_metrics").select("queue_size, processing_time_seconds, throughput, recorded_at").eq("industry", industry).eq("stage", sn).gte("recorded_at", cutoff).execute()
                if not resp.data:
                    return f"No data for '{sn}'."
                breaches = []
                for row in resp.data:
                    if row["queue_size"] > thresholds["queue"] or row["processing_time_seconds"] > thresholds["processing"] or row["throughput"] < thresholds["throughput"]:
                        ts = datetime.fromisoformat(row["recorded_at"].replace("Z", "+00:00"))
                        breaches.append({"hour": ts.hour, "dow": int(ts.strftime("%w"))})
                if not breaches:
                    return f"'{sn}' has no breaches in 30 days."
                hc: dict = defaultdict(int)
                dc: dict = defaultdict(int)
                for b in breaches:
                    hc[b["hour"]] += 1
                    dc[b["dow"]] += 1
                ph = max(hc, key=lambda h: hc[h])
                pd = max(dc, key=lambda d: dc[d])
                hl = f"{'12' if ph == 12 else ph % 12 or 12}{'am' if ph < 12 else 'pm'}"
                dn = ["Sunday","Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"]
                return f"'{sn}': {len(breaches)} breaches in 30 days. Peak: {hl} ({round(hc[ph]/len(breaches)*100)}%). Peak day: {dn[pd]}s ({round(dc[pd]/len(breaches)*100)}%)."
            else:
                return f"Unknown tool: {tool_name}"
        except Exception as e:
            return f"Tool error ({tool_name}): {str(e)}"

    system_prompt = f"""You are an AI operations intelligence agent for a {industry} operation.
Industry context: {get_industry_ai_context(industry)}
Investigate systematically:
1. check_health_scores first
2. get_open_incidents
3. get_cascade_predictions
4. get_eta_to_breach
5. get_recurring_patterns for any critical/severe stage
Then write: CRITICAL ISSUES / WARNING ISSUES / RECOMMENDED ACTIONS.
For construction, emphasize permit delays, inspection backlog, blocked downstream work, subcontractor coordination, and handover risk."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": goal},
    ]

    parsed_steps = []
    output = "Investigation complete."

    try:
        with httpx.Client(timeout=90.0) as client:
            for _ in range(10):
                resp = client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
                    json={"model": "llama-3.3-70b-versatile", "messages": messages, "tools": AGENT_TOOLS, "tool_choice": "auto", "max_tokens": 1500},
                )
                if resp.status_code == 429:
                    raise HTTPException(status_code=429, detail="GROQ_RATE_LIMIT: Rate limited. Wait 60 seconds.")
                resp.raise_for_status()
                data = resp.json()
                if not isinstance(data, dict):
                    logger.error("Legacy agent investigation received non-dict response for industry=%s: %r", industry, data)
                    output = "AI provider returned an invalid response. Please try again."
                    break
                choices = data.get("choices") or []
                if not choices:
                    output = "Empty response from AI. Try again."
                    break
                choice = choices[0] or {}
                if not isinstance(choice, dict):
                    logger.error("Legacy agent investigation received invalid choice for industry=%s: %r", industry, choice)
                    output = "AI provider returned an invalid choice payload. Please try again."
                    break
                message = choice.get("message") or {}
                if not isinstance(message, dict):
                    logger.error("Legacy agent investigation received invalid message for industry=%s: %r", industry, message)
                    output = "AI provider returned an invalid message payload. Please try again."
                    break
                tool_calls = message.get("tool_calls") or []
                assistant_message = {
                    "role": message.get("role") or "assistant",
                    "content": message.get("content") or "",
                }
                if tool_calls:
                    assistant_message["tool_calls"] = tool_calls
                messages.append(assistant_message)
                if not tool_calls:
                    output = message.get("content") or "Investigation complete."
                    break
                for tc in tool_calls:
                    if not isinstance(tc, dict):
                        logger.warning("Skipping invalid legacy tool call for industry=%s: %r", industry, tc)
                        continue
                    fn = tc.get("function") or {}
                    if not isinstance(fn, dict):
                        logger.warning("Skipping invalid legacy function payload for industry=%s: %r", industry, fn)
                        continue
                    tn = fn.get("name", "")
                    try:
                        ta = _json.loads(fn.get("arguments") or "{}")
                    except Exception:
                        ta = {}
                    finding = _execute_tool(tn, ta)
                    parsed_steps.append({"step": len(parsed_steps) + 1, "tool": tn, "input": str(ta.get("stage_name", "")), "finding": str(finding)[:500]})
                    messages.append({"role": "tool", "tool_call_id": tc.get("id", ""), "content": str(finding)})

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")

    ol = output.lower()
    dps = []
    if any(w in ol for w in ["critical", "severe", "breached", "immediate"]):
        dps.append({"id": "acknowledge_critical", "type": "acknowledge", "question": "The agent found critical issues. Do you want to acknowledge these and flag them for the ops team?", "action": "trigger_alerts"})
    if any(w in ol for w in ["recurring", "pattern", "breaches in 30"]):
        dps.append({"id": "generate_playbook", "type": "playbook", "question": "Recurring failure patterns were detected. Do you want to auto-generate playbooks for affected stages?", "action": "generate_playbooks"})
    if "cascade" in ol:
        dps.append({"id": "cascade_alert", "type": "alert", "question": "A cascade risk was detected. Do you want to note this for the ops team?", "action": "send_cascade_alert"})
    dps.append({"id": "log_investigation", "type": "audit", "question": "Log this investigation to the audit trail?", "action": "log_audit"})

    return {"success": True, "industry": industry, "goal": goal, "steps": parsed_steps, "output": output, "decision_points": dps, "investigated_at": datetime.now(timezone.utc).isoformat()}


@app.post("/agent/decision")
async def agent_decision(body: AgentDecisionRequest):
    """
    Handle a human decision in response to an agent finding.
    The agent proposed an action — the user approved or rejected it.
    """
    logger.info("Agent decision requested for decision_id=%s approved=%s industry=%s", body.decision_id, body.approved, body.industry)
    if not body.approved:
        return {"success": True, "decision_id": body.decision_id, "action": "skipped", "message": "User chose to skip this action."}

    result = {"success": True, "decision_id": body.decision_id, "approved": True, "action_taken": None}

    if body.decision_id == "generate_playbook" and body.stage:
        try:
            playbook = await generate_playbook(body.stage, body.industry)
            result["action_taken"] = "playbook_generated"
            result["playbook"] = playbook
        except Exception as e:
            logger.exception("Failed to generate playbook for decision_id=%s stage=%s industry=%s", body.decision_id, body.stage, body.industry)
            result["action_taken"] = "playbook_failed"
            result["error"] = str(e)

    elif body.decision_id == "log_investigation":
        supabase.table("analysis_logs").insert({
            "incident_id": None,
            "ai_analysis": f"[AGENT INVESTIGATION] {body.investigation_output[:1000]}",
            "triggered_by": "agent_investigation",
            "confidence_score": 75,
        }).execute()
        result["action_taken"] = "investigation_logged"

    elif body.decision_id == "acknowledge_critical":
        result["action_taken"] = "critical_acknowledged"
        result["message"] = "Critical issues acknowledged. Check the dashboard for open incidents."

    elif body.decision_id == "cascade_alert":
        result["action_taken"] = "cascade_alert_noted"
        result["message"] = "Cascade alert noted. Monitor the cascade predictions tab closely."

    return result


# ─── Custom analysis + Webhook ────────────────────────────────────────────────

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
    if not rows: raise HTTPException(status_code=400, detail="No data provided")
    thresholds = INDUSTRY_THRESHOLDS.get(body.industry, {"queue": 50, "processing": 300, "throughput": 10})
    issues = []
    for r in rows:
        row_issues = []
        if r.queue_size > thresholds["queue"]: row_issues.append(f"queue backed up ({r.queue_size}, threshold: {thresholds['queue']})")
        if r.processing_time_seconds > thresholds["processing"]: row_issues.append(f"processing too high ({r.processing_time_seconds}s)")
        if r.throughput < thresholds["throughput"]: row_issues.append(f"throughput critically low ({r.throughput}/hr)")
        if row_issues: issues.append({"stage": r.stage, "issues": row_issues})
    rows_text = "\n".join(f"- {r.stage}: Queue {r.queue_size} | Processing {r.processing_time_seconds}s | Throughput {r.throughput}/hr" for r in rows)
    issues_text = "\n".join(f"- {i['stage']}: {', '.join(i['issues'])}" for i in issues) if issues else "No violations."
    prompt = (
        f"Senior ops analyst.\nIndustry: {body.industry}.\n"
        f"Industry context: {get_industry_ai_context(body.industry)}\n"
        f"Workflow:\n{rows_text}\n"
        f"Violations:\n{issues_text}\n"
        f"Preferred action themes: {get_stage_specific_actions(body.industry, rows[0].stage if rows else '')}\n"
        "1. Worst bottleneck with numbers\n2. Cascade impact\n3. 3 actions in 30 min."
    )
    ai_analysis = await call_groq(prompt)
    return {"detected_issues": issues, "ai_analysis": ai_analysis}


@app.post("/extract-and-analyze")
async def extract_and_analyze(
    file: UploadFile = File(...),
    industry: str = Form(default="operations"),
):
    filename = file.filename or ""
    content_type = file.content_type or ""
    raw_bytes = await file.read()
    csv_text = ""

    if filename.endswith(".csv") or "csv" in content_type:
        try:
            csv_text = raw_bytes.decode("utf-8", errors="replace")
        except Exception:
            raise HTTPException(status_code=400, detail="Could not read CSV file.")
    elif filename.endswith((".xlsx", ".xls")) or "excel" in content_type or "spreadsheet" in content_type:
        try:
            import openpyxl
            wb = openpyxl.load_workbook(io.BytesIO(raw_bytes), read_only=True)
            ws = wb.active
            rows = []
            for i, row in enumerate(ws.iter_rows(values_only=True)):
                if i > 200:
                    break
                rows.append(",".join(str(c) if c is not None else "" for c in row))
            csv_text = "\n".join(rows)
        except ImportError:
            raise HTTPException(status_code=500, detail="openpyxl not installed.")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Could not read Excel file: {str(e)}")
    else:
        try:
            csv_text = raw_bytes.decode("utf-8", errors="replace")
        except Exception:
            raise HTTPException(status_code=400, detail="Unsupported file format. Please upload CSV or Excel.")

    if not csv_text.strip():
        raise HTTPException(status_code=400, detail="File appears to be empty.")

    lines = csv_text.strip().split("\n")
    preview = "\n".join(lines[:100])
    thresholds = INDUSTRY_THRESHOLDS.get(industry, {"queue": 50, "processing": 300, "throughput": 10})

    extraction_prompt = f"""You are a data analyst. A user uploaded a file with operational workflow data for a {industry} operation.
Industry context: {get_industry_ai_context(industry)}

Raw file content (first 100 rows):
{preview}

Your job:
1. Identify which columns correspond to: stage name, queue size, processing time (in seconds), throughput (per hour)
2. If processing time is in minutes, convert to seconds. If throughput is per day, convert to per hour.
3. Extract data rows and return ONLY valid JSON in this exact format with no explanation or markdown:

{{"column_mapping": {{"stage": "col name", "queue_size": "col name", "processing_time_seconds": "col name", "throughput": "col name"}}, "rows": [{{"stage": "name", "queue_size": 0.0, "processing_time_seconds": 0.0, "throughput": 0.0}}], "notes": "observations about the data"}}

Extract up to 20 rows. Return ONLY the JSON object."""

    extraction_response = await call_groq(extraction_prompt, max_tokens=1500)

    import json as _j
    import re as _re
    clean = extraction_response.strip()
    clean = _re.sub(r'^```(?:json)?\s*', '', clean)
    clean = _re.sub(r'\s*```$', '', clean)
    clean = clean.strip()

    try:
        extracted = _j.loads(clean)
    except Exception:
        match = _re.search(r'\{.*\}', clean, _re.DOTALL)
        if match:
            try:
                extracted = _j.loads(match.group())
            except Exception:
                raise HTTPException(status_code=422, detail="AI could not parse your file. Please ensure it has column headers and data rows.")
        else:
            raise HTTPException(status_code=422, detail="AI could not parse your file. Please ensure it has column headers and data rows.")

    rows_data = extracted.get("rows", [])
    column_mapping = extracted.get("column_mapping", {})
    notes = extracted.get("notes", "")

    if not rows_data:
        raise HTTPException(status_code=422, detail="No data rows could be extracted from your file.")

    issues = []
    for r in rows_data:
        stage = str(r.get("stage", "unknown"))
        queue = float(r.get("queue_size", 0) or 0)
        processing = float(r.get("processing_time_seconds", 0) or 0)
        throughput = float(r.get("throughput", 0) or 0)
        row_issues = []
        if queue > thresholds["queue"]:
            row_issues.append(f"queue backed up ({queue} items, threshold: {thresholds['queue']})")
        if processing > thresholds["processing"]:
            row_issues.append(f"processing time too high ({processing}s, threshold: {thresholds['processing']}s)")
        if throughput > 0 and throughput < thresholds["throughput"]:
            row_issues.append(f"throughput critically low ({throughput}/hr, threshold: {thresholds['throughput']}/hr)")
        if row_issues:
            issues.append({"stage": stage, "issues": row_issues})

    rows_text = "\n".join(f"- Stage: {r.get('stage')} | Queue: {r.get('queue_size')} | Processing: {r.get('processing_time_seconds')}s | Throughput: {r.get('throughput')}/hr" for r in rows_data)
    issues_text = "\n".join(f"- {i['stage']}: {', '.join(i['issues'])}" for i in issues) if issues else "No threshold violations detected."

    analysis_prompt = (
        f"Senior ops analyst. A {industry} team uploaded their operational data.\n"
        f"Industry context: {get_industry_ai_context(industry)}\n\n"
        f"Extracted data ({len(rows_data)} rows):\n{rows_text}\n\n"
        f"Violations:\n{issues_text}\n\n"
        f"Column interpretation: {notes}\n\n"
        f"Preferred action themes: {get_stage_specific_actions(industry, str(rows_data[0].get('stage', '')) if rows_data else '')}\n\n"
        "1. Worst bottleneck with actual numbers\n2. Cascade impact\n3. 3 specific actions in next 30 min. No generic advice."
    )
    ai_analysis = await call_groq(analysis_prompt, max_tokens=600)

    return {"success": True, "filename": filename, "rows_extracted": len(rows_data), "column_mapping": column_mapping, "notes": notes, "detected_issues": issues, "ai_analysis": ai_analysis, "rows": rows_data}


@app.post("/copilot/chat")
async def copilot_chat(body: CopilotChatRequest):
    message = (body.message or "").strip()
    if not message:
        return {"success": False, "error": "Message is required."}

    role = (body.role or "ops").strip().lower()
    if role not in {"ops", "leadership", "engineering"}:
        role = "ops"

    safe_increment_platform_metric("copilot_questions")

    try:
        context, sources = build_copilot_context(body.industry, message, body.incident_id)
        role_instructions = {
            "ops": "Prioritize practical next steps, immediate risks, and operator-friendly language.",
            "leadership": "Prioritize business impact, urgency, exposure, and concise executive framing.",
            "engineering": "Prioritize bottleneck mechanics, thresholds, system behavior, and signal interpretation.",
        }
        prompt = (
            "You are Ops Copilot for an internal operations intelligence platform.\n"
            f"Role mode: {role}.\n"
            f"{role_instructions[role]}\n"
            "Answer only from the platform context below. Do not use outside knowledge. "
            "If the question is not supported by the provided platform context, say so clearly.\n\n"
            "Write the answer with these sections:\n"
            "Direct answer\nWhy the platform thinks this\nRecommended next step\nSuggested follow-ups\n\n"
            f"Platform context:\n{context}\n\n"
            f"User question: {message}"
        )
        answer = await call_groq(prompt, max_tokens=700)
        confidence_score, _ = extract_confidence(answer)
        suggested_followups = [
            "What should ops do next?",
            "What is the downstream impact?",
            "Summarize for leadership",
        ]
        if "compare" in message.lower() or "bottleneck" in message.lower():
            suggested_followups = [
                "Compare bottlenecks by severity",
                "Which stage is most likely to cascade next?",
                "What threshold is driving this risk?",
            ]
        return {
            "success": True,
            "answer": answer,
            "confidence": round(confidence_score / 100, 2),
            "sources": sources,
            "suggested_followups": suggested_followups,
        }
    except HTTPException as exc:
        return {"success": False, "error": exc.detail}
    except Exception:
        logger.exception("Copilot chat failed for industry=%s role=%s", body.industry, role)
        return {"success": False, "error": "Copilot could not complete the request."}


class SuggestionPayload(BaseModel):
    category: str
    title: str
    description: Optional[str] = None

@app.post("/suggestions")
async def submit_suggestion(body: SuggestionPayload):
    if not body.title.strip():
        raise HTTPException(status_code=400, detail="Title is required")
    result = supabase.table("suggestions").insert({
        "category": body.category,
        "title": body.title.strip(),
        "description": body.description.strip() if body.description else None,
    }).execute()
    return {"success": True, "id": result.data[0]["id"] if result.data else None}

@app.get("/suggestions")
def get_suggestions():
    response = (
        supabase.table("suggestions")
        .select("*")
        .order("submitted_at", desc=True)
        .execute()
    )
    return {"suggestions": response.data}


@app.post("/fetch-live-data")
async def fetch_live_data(industry: str = "all"):
    safe_increment_platform_metric("live_data_refresh_calls")
    try:
        bundle = await fetch_live_incident_bundle(industry)
        results = {}
        all_incidents = []
        mode_counts = {"live": 0, "fallback": 0}

        for ind, result in bundle.get("industries", {}).items():
            incidents = result.get("incidents", [])
            metric_events = result.get("metric_events", [])
            inserted_incidents = 0
            inserted_metrics = 0
            fetched_at = datetime.now(timezone.utc).isoformat()
            route_error = result.get("error")

            try:
                if ind in SUPPORTED_LIVE_INDUSTRIES:
                    clear_demo_incidents_for_live_industry(ind)
            except Exception as exc:
                logger.exception("Failed to clear prior demo incidents for %s", ind)
                route_error = route_error or f"Demo incident cleanup failed: {str(exc)}"

            for metric_event in metric_events:
                try:
                    insert_live_metric_record(metric_event)
                    inserted_metrics += 1
                except Exception as exc:
                    logger.exception("Failed to persist live metric event for %s", ind)
                    route_error = route_error or f"Metric persistence failed: {str(exc)}"

            for live_incident in incidents:
                try:
                    stored = upsert_live_incident_record(live_incident)
                    if stored:
                        inserted_incidents += 1
                        if is_elevated_severity(live_incident.get("severity", "")):
                            try:
                                await send_alert_email(stored)
                                await send_slack_alert(
                                    stage=stored.get("stage", live_incident.get("affected_system", "")),
                                    severity="high" if live_incident.get("severity") == "critical" else live_incident.get("severity", "high"),
                                    description=stored.get("description", live_incident.get("description", "")),
                                    industry=ind,
                                )
                            except Exception:
                                logger.exception("Failed to send live-data alert notifications for %s", ind)
                except Exception as exc:
                    logger.exception("Failed to persist live incident for %s", ind)
                    route_error = route_error or f"Incident persistence failed: {str(exc)}"

            mode_counts[result.get("data_mode", "fallback")] = mode_counts.get(result.get("data_mode", "fallback"), 0) + 1
            all_incidents.extend(incidents)
            source_systems = result.get("source_systems", [])
            results[ind] = {
                "supported": result.get("supported", True),
                "data_mode": result.get("data_mode", "fallback"),
                "incident_count": len(incidents),
                "metric_count": inserted_metrics,
                "stored_incident_count": inserted_incidents,
                "source_systems": source_systems,
                "source_system": source_systems[0] if source_systems else None,
                "error": route_error,
                "fetched_at": fetched_at,
                "incidents": incidents,
            }

        return format_live_data_response(industry, results, all_incidents, mode_counts)
    except Exception as exc:
        logger.exception("Unhandled fetch-live-data failure for industry=%s", industry)
        return build_route_level_fallback_response(industry, str(exc))


@app.get("/connect-info")
def get_connect_info():
    """Returns connection info and code snippets for users to connect real data."""
    backend_url = "https://ops-intelligence-platform.onrender.com"
    return {
        "webhook_url": f"{backend_url}/webhook/events",
        "docs_url": f"{backend_url}/docs",
        "curl_example": f"""curl -X POST {backend_url}/webhook/events \\
  -H "Content-Type: application/json" \\
  -d '{{
    "events": [{{
      "stage": "your_stage_name",
      "queue_size": 45,
      "processing_time_seconds": 280,
      "throughput": 8,
      "industry": "healthcare"
    }}]
  }}'""",
        "python_example": f"""import httpx

httpx.post("{backend_url}/webhook/events", json={{
    "events": [{{
        "stage": "your_stage_name",
        "queue_size": 45,
        "processing_time_seconds": 280,
        "throughput": 8,
        "industry": "healthcare"
    }}]
}})""",
        "javascript_example": f"""fetch("{backend_url}/webhook/events", {{
  method: "POST",
  headers: {{ "Content-Type": "application/json" }},
  body: JSON.stringify({{
    events: [{{
      stage: "your_stage_name",
      queue_size: 45,
      processing_time_seconds: 280,
      throughput: 8,
      industry: "healthcare"
    }}]
  }})
}})""",
    }


@app.post("/test-webhook")
async def test_webhook(industry: str = "healthcare"):
    """Send a test event to verify webhook connectivity."""
    import random
    stages = {
        "healthcare": [("ed_triage", 25, 150, 8), ("bed_assignment", 18, 200, 5)],
        "cruise": [("baggage_drop", 60, 400, 7), ("security_check", 55, 320, 8)],
        "construction": [("permits_approvals", 6, 86400, 1), ("inspection", 5, 28800, 1), ("mep_rough_in", 4, 21600, 1)],
        "banking": [("loan_verification", 120, 650, 4), ("kyc_check", 110, 700, 3)],
        "airport": [("checkin", 90, 250, 18), ("security_screening", 85, 260, 17)],
        "energy": [("generation_dispatch", 28, 360, 3), ("load_balancing", 22, 330, 4)],
        "water": [("treatment_filtration", 18, 720, 2), ("distribution_pumping", 16, 680, 2)],
        "weather": [("storm_response", 35, 1200, 1), ("flood_response", 28, 1500, 1)],
        "civil": [("earthworks", 10, 500, 1), ("quality_check", 9, 490, 1)],
        "architecture": [("design_review", 12, 750, 0), ("permit_submission", 11, 760, 0)],
        "ecommerce": [("warehouse_pick", 220, 190, 48), ("dispatch", 210, 185, 47)],
    }
    stage_data = stages.get(industry, stages["healthcare"])
    stage_name, base_queue, base_proc, base_throughput = random.choice(stage_data)
    queue = base_queue + random.randint(-5, 15)
    proc = base_proc + random.randint(-20, 80)
    throughput = max(0, base_throughput + random.randint(-3, 1))

    payload = WebhookPayload(events=[WebhookEvent(
        stage=stage_name,
        queue_size=float(queue),
        processing_time_seconds=float(proc),
        throughput=float(throughput),
        industry=industry,
        source="test",
    )])
    result = await receive_webhook(payload)
    return {
        "success": True,
        "message": f"Test event sent for {stage_name} ({industry})",
        "data_sent": {"stage": stage_name, "queue_size": queue, "processing_time_seconds": proc, "throughput": throughput},
        "result": result,
    }


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
    api_key: Optional[str] = None

@app.post("/webhook/events")
async def receive_webhook(payload: WebhookPayload):
    safe_increment_platform_metric("webhook_events_received")
    if WEBHOOK_SECRET and payload.secret != WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Invalid secret")
    # Resolve user from API key
    webhook_user_id = None
    if payload.api_key:
        key_resp = supabase.table("user_api_keys").select("user_id").eq("api_key", payload.api_key).limit(1).execute()
        if key_resp.data:
            webhook_user_id = key_resp.data[0]["user_id"]
    created = []
    for event in payload.events:
        industry = event.industry
        thresholds = INDUSTRY_THRESHOLDS.get(industry, {"queue": 50, "processing": 300, "throughput": 10})
        violations = []
        if event.queue_size > thresholds["queue"]:
            violations.append(f"Queue {event.queue_size} exceeds {thresholds['queue']}")
        if event.processing_time_seconds > thresholds["processing"]:
            violations.append(f"Processing {event.processing_time_seconds}s exceeds {thresholds['processing']}s")
        if event.throughput < thresholds["throughput"]:
            violations.append(f"Throughput {event.throughput}/hr below {thresholds['throughput']}/hr")
        health = max(0, min(100, 100 - (event.queue_size / thresholds["queue"] * 30) - (event.processing_time_seconds / thresholds["processing"] * 30) + (min(event.throughput, thresholds["throughput"]) / thresholds["throughput"] * 10)))
        supabase.table("workflow_metrics").insert({"industry": industry, "stage": event.stage, "queue_size": event.queue_size, "processing_time_seconds": event.processing_time_seconds, "throughput": event.throughput, "health_score": round(health, 1)}).execute()
        if violations:
            severity = "high" if len(violations) >= 2 else "medium"
            if industry == "construction":
                metric_summary = describe_metric_signal(industry, event.stage, event.queue_size, event.processing_time_seconds, event.throughput)
                recommendations = get_stage_specific_actions(industry, event.stage)
                violation_text = f"{metric_summary} Triggered metrics: {'; '.join(violations)}. Recommended next moves: {recommendations}."
            else:
                violation_text = ". ".join(violations)
            # Alert correlation — check for existing open incident in last 30 min
            cutoff = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
            existing = supabase.table("incidents").select("id, description").eq(
                "industry", industry
            ).eq("stage", event.stage).eq("status", "open").gte(
                "created_at", cutoff
            ).limit(1).execute()

            if existing.data:
                # Update existing incident instead of creating duplicate
                existing_id = existing.data[0]["id"]
                supabase.table("incidents").update({
                    "description": violation_text,
                    "severity": severity,
                }).eq("id", existing_id).execute()
            else:
                # Create new incident
                inc = supabase.table("incidents").insert({
                    "stage": event.stage,
                    "severity": severity,
                    "description": violation_text,
                    "status": "open",
                    "industry": industry,
                    "user_id": webhook_user_id,
                }).execute()
                if inc.data:
                    created.append(inc.data[0])
                    # Slack alert for new HIGH incidents
                    if severity == "high":
                        await send_slack_alert(
                            stage=event.stage,
                            severity=severity,
                            description=violation_text,
                            industry=industry,
                            health=round(health, 1),
                        )
    return {"received": len(payload.events), "incidents_created": len(created)}
