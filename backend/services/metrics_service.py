import os
from datetime import datetime
import logging

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
FALLBACK_METRICS_INDUSTRY = "__platform_metrics__"


def _get_supabase() -> Client:
    global _supabase
    if _supabase is None:
        _supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
    return _supabase


def _is_missing_table_error(error: Exception) -> bool:
    return "platform_metrics" in str(error).lower() and "not found" in str(error).lower()


def _log_metrics_error(action: str, error: Exception, metric_name: str | None = None) -> None:
    metric_hint = f" for '{metric_name}'" if metric_name else ""
    logger.exception("Platform metrics %s failed%s", action, metric_hint)
    if _is_missing_table_error(error):
        logger.error("The 'platform_metrics' table appears to be missing. Apply platform_metrics.sql in Supabase.")


def _get_fallback_metric_value(metric_name: str, initial_value: int = 0) -> int:
    supabase = _get_supabase()
    response = (
        supabase.table("workflow_metrics")
        .select("queue_size")
        .eq("industry", FALLBACK_METRICS_INDUSTRY)
        .eq("stage", metric_name)
        .order("recorded_at", desc=True)
        .limit(1)
        .execute()
    )
    if response.data:
        return int(response.data[0].get("queue_size", initial_value) or initial_value)
    return initial_value


def _set_fallback_metric_value(metric_name: str, value: int) -> int:
    supabase = _get_supabase()
    safe_value = max(0, value)
    existing = (
        supabase.table("workflow_metrics")
        .select("stage")
        .eq("industry", FALLBACK_METRICS_INDUSTRY)
        .eq("stage", metric_name)
        .limit(1)
        .execute()
    )
    payload = {
        "industry": FALLBACK_METRICS_INDUSTRY,
        "stage": metric_name,
        "queue_size": safe_value,
        "processing_time_seconds": 0,
        "throughput": 0,
        "health_score": min(100, safe_value),
    }
    if existing.data:
        (
            supabase.table("workflow_metrics")
            .update(payload)
            .eq("industry", FALLBACK_METRICS_INDUSTRY)
            .eq("stage", metric_name)
            .execute()
        )
    else:
        supabase.table("workflow_metrics").insert(payload).execute()
    return safe_value


def _get_fallback_metric_map() -> dict[str, int]:
    supabase = _get_supabase()
    response = (
        supabase.table("workflow_metrics")
        .select("stage, queue_size, recorded_at")
        .eq("industry", FALLBACK_METRICS_INDUSTRY)
        .order("recorded_at", desc=True)
        .execute()
    )
    metric_map: dict[str, int] = {}
    for row in response.data or []:
        stage = row.get("stage")
        if not stage or stage in metric_map:
            continue
        metric_map[stage] = int(row.get("queue_size", 0) or 0)
    return metric_map


def _upsert_metric(metric_name: str, metric_value: int) -> None:
    supabase = _get_supabase()
    supabase.table("platform_metrics").upsert(
        {
            "metric_name": metric_name,
            "metric_value": max(0, metric_value),
            "updated_at": datetime.utcnow().isoformat(),
        },
        on_conflict="metric_name",
    ).execute()


def _ensure_core_metrics() -> None:
    for metric_name in (*CORE_METRIC_NAMES, _today_metric_name()):
        _upsert_metric(metric_name, 0)


def _ensure_metric(metric_name: str, initial_value: int = 0) -> int:
    try:
        supabase = _get_supabase()
        response = supabase.table("platform_metrics").select("id, metric_value").eq("metric_name", metric_name).limit(1).execute()
        if response.data:
            return int(response.data[0].get("metric_value", initial_value) or initial_value)

        _upsert_metric(metric_name, initial_value)
        return initial_value
    except Exception as error:
        _log_metrics_error("ensure", error, metric_name)
        if _is_missing_table_error(error):
            return _set_fallback_metric_value(metric_name, _get_fallback_metric_value(metric_name, initial_value))
        raise


def increment_metric(metric_name: str, amount: int = 1) -> int:
    try:
        supabase = _get_supabase()
        current_value = _ensure_metric(metric_name, 0)
        new_value = max(0, current_value + amount)
        supabase.table("platform_metrics").update({
            "metric_value": new_value,
            "updated_at": datetime.utcnow().isoformat(),
        }).eq("metric_name", metric_name).execute()
        return new_value
    except Exception as error:
        _log_metrics_error("increment", error, metric_name)
        if _is_missing_table_error(error):
            current_value = _get_fallback_metric_value(metric_name, 0)
            return _set_fallback_metric_value(metric_name, current_value + amount)
        raise


def set_metric(metric_name: str, value: int) -> int:
    try:
        supabase = _get_supabase()
        _ensure_metric(metric_name, 0)
        safe_value = max(0, value)
        supabase.table("platform_metrics").update({
            "metric_value": safe_value,
            "updated_at": datetime.utcnow().isoformat(),
        }).eq("metric_name", metric_name).execute()
        return safe_value
    except Exception as error:
        _log_metrics_error("set", error, metric_name)
        if _is_missing_table_error(error):
            return _set_fallback_metric_value(metric_name, value)
        raise


def get_metric_value(metric_name: str) -> int:
    return _ensure_metric(metric_name, 0)


def _today_metric_name() -> str:
    return f"visitors_today_{datetime.utcnow().strftime('%Y%m%d')}"


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
        supabase = _get_supabase()
        _ensure_core_metrics()
        response = supabase.table("platform_metrics").select("metric_name, metric_value").execute()
        rows = response.data or []
        metric_map = {row["metric_name"]: int(row.get("metric_value", 0) or 0) for row in rows}
    except Exception as error:
        _log_metrics_error("snapshot", error)
        if _is_missing_table_error(error):
            for metric_name in (*CORE_METRIC_NAMES, _today_metric_name()):
                _set_fallback_metric_value(metric_name, _get_fallback_metric_value(metric_name, 0))
            metric_map = _get_fallback_metric_map()
        else:
            raise

    top_industries = []
    for metric_name, metric_value in metric_map.items():
        if metric_name.startswith("industry_selected_"):
            top_industries.append({
                "industry": metric_name.removeprefix("industry_selected_"),
                "count": metric_value,
            })
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
