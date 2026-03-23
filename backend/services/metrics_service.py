import os
from datetime import datetime

from supabase import Client, create_client


_supabase: Client | None = None


def _get_supabase() -> Client:
    global _supabase
    if _supabase is None:
        _supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
    return _supabase


def _ensure_metric(metric_name: str, initial_value: int = 0) -> int:
    supabase = _get_supabase()
    response = supabase.table("platform_metrics").select("id, metric_value").eq("metric_name", metric_name).limit(1).execute()
    if response.data:
        return int(response.data[0].get("metric_value", initial_value) or initial_value)

    supabase.table("platform_metrics").insert({
        "metric_name": metric_name,
        "metric_value": initial_value,
    }).execute()
    return initial_value


def increment_metric(metric_name: str, amount: int = 1) -> int:
    supabase = _get_supabase()
    current_value = _ensure_metric(metric_name, 0)
    new_value = max(0, current_value + amount)
    supabase.table("platform_metrics").update({
        "metric_value": new_value,
        "updated_at": datetime.utcnow().isoformat(),
    }).eq("metric_name", metric_name).execute()
    return new_value


def set_metric(metric_name: str, value: int) -> int:
    supabase = _get_supabase()
    _ensure_metric(metric_name, 0)
    safe_value = max(0, value)
    supabase.table("platform_metrics").update({
        "metric_value": safe_value,
        "updated_at": datetime.utcnow().isoformat(),
    }).eq("metric_name", metric_name).execute()
    return safe_value


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
    supabase = _get_supabase()
    response = supabase.table("platform_metrics").select("metric_name, metric_value").execute()
    rows = response.data or []
    metric_map = {row["metric_name"]: int(row.get("metric_value", 0) or 0) for row in rows}

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
        "industries_explored": metric_map.get("industries_explored", 0),
        "top_industries_explored": top_industries[:3],
    }
