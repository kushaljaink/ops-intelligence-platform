import logging
import os
from datetime import datetime, timezone

from supabase import Client, create_client


_supabase: Client | None = None
logger = logging.getLogger(__name__)

CORE_METRIC_NAMES = (
    "active_sessions",
    "incidents_analyzed",
    "agent_investigations",
    "webhook_events_received",
    "live_data_refresh_calls",
    "industries_explored",
)
METRICS_INDUSTRY = "__platform_metrics__"


def _get_supabase() -> Client:
    global _supabase
    if _supabase is None:
        _supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
    return _supabase


def _today_metric_name() -> str:
    return f"visitors_today_{datetime.now(timezone.utc).strftime('%Y%m%d')}"


def _normalize_metric_value(value: int) -> int:
    return max(0, int(value))


def _metric_payload(metric_name: str, metric_value: int) -> dict:
    safe_value = _normalize_metric_value(metric_value)
    return {
        "industry": METRICS_INDUSTRY,
        "stage": metric_name,
        "queue_size": safe_value,
        "processing_time_seconds": 0,
        "throughput": 0,
        "health_score": min(100, safe_value),
    }


def _set_metric_value(metric_name: str, metric_value: int) -> int:
    supabase = _get_supabase()
    payload = _metric_payload(metric_name, metric_value)
    existing = (
        supabase.table("workflow_metrics")
        .select("id")
        .eq("industry", METRICS_INDUSTRY)
        .eq("stage", metric_name)
        .limit(1)
        .execute()
    )
    if existing.data:
        (
            supabase.table("workflow_metrics")
            .update(payload)
            .eq("industry", METRICS_INDUSTRY)
            .eq("stage", metric_name)
            .execute()
        )
    else:
        supabase.table("workflow_metrics").insert(payload).execute()
    return payload["queue_size"]


def _get_metric_map() -> dict[str, int]:
    supabase = _get_supabase()
    response = (
        supabase.table("workflow_metrics")
        .select("stage, queue_size, recorded_at")
        .eq("industry", METRICS_INDUSTRY)
        .order("recorded_at", desc=True)
        .execute()
    )
    metric_map: dict[str, int] = {}
    for row in response.data or []:
        stage = row.get("stage")
        if not stage or stage in metric_map:
            continue
        metric_map[stage] = _normalize_metric_value(row.get("queue_size", 0) or 0)
    return metric_map


def _ensure_metric(metric_name: str, initial_value: int = 0) -> int:
    metric_map = _get_metric_map()
    if metric_name in metric_map:
        return metric_map[metric_name]
    return _set_metric_value(metric_name, initial_value)


def _ensure_core_metrics() -> None:
    for metric_name in (*CORE_METRIC_NAMES, _today_metric_name()):
        _ensure_metric(metric_name, 0)


def increment_metric(metric_name: str, amount: int = 1) -> int:
    try:
        current_value = _ensure_metric(metric_name, 0)
        return _set_metric_value(metric_name, current_value + amount)
    except Exception:
        logger.exception("Platform metrics increment failed for '%s'", metric_name)
        raise


def set_metric(metric_name: str, value: int) -> int:
    try:
        return _set_metric_value(metric_name, value)
    except Exception:
        logger.exception("Platform metrics set failed for '%s'", metric_name)
        raise


def get_metric_value(metric_name: str) -> int:
    return _ensure_metric(metric_name, 0)


def record_visitor_session_start() -> dict:
    visitors_today = increment_metric(_today_metric_name(), 1)
    active_sessions = increment_metric("active_sessions", 1)
    return {
        "visitors_today": visitors_today,
        "active_sessions": active_sessions,
    }


def record_visitor_session_end() -> int:
    current = get_metric_value("active_sessions")
    return set_metric("active_sessions", max(0, current - 1))


def record_industry_selection(industry: str) -> dict:
    sanitized = (industry or "unknown").strip().lower().replace(" ", "_")
    total = increment_metric("industries_explored", 1)
    per_industry = increment_metric(f"industry_selected_{sanitized}", 1)
    return {
        "industries_explored": total,
        "industry": sanitized,
        "industry_count": per_industry,
    }


def get_metrics_snapshot() -> dict:
    try:
        _ensure_core_metrics()
        metric_map = _get_metric_map()
    except Exception:
        logger.exception("Platform metrics snapshot failed")
        raise

    top_industries = []
    for metric_name, metric_value in metric_map.items():
        if metric_name.startswith("industry_selected_"):
            top_industries.append(
                {
                    "industry": metric_name.removeprefix("industry_selected_"),
                    "count": metric_value,
                }
            )
    top_industries.sort(key=lambda item: item["count"], reverse=True)

    return {
        "visitors_today": metric_map.get(_today_metric_name(), 0),
        "active_sessions": metric_map.get("active_sessions", 0),
        "incidents_analyzed": metric_map.get("incidents_analyzed", 0),
        "agent_investigations": metric_map.get("agent_investigations", 0),
        "webhook_events_received": metric_map.get("webhook_events_received", 0),
        "live_data_refresh_calls": metric_map.get("live_data_refresh_calls", 0),
        "live_refresh_calls": metric_map.get("live_data_refresh_calls", 0),
        "industries_explored": metric_map.get("industries_explored", 0),
        "top_industries_explored": top_industries[:3],
    }
