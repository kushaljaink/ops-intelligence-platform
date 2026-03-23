"""
ops_agent.py — AI Agent using Groq's native tool-calling API.
No LangChain. Pure Groq function calling.
"""

import httpx
import json
import logging
import time
from supabase import Client
from datetime import datetime, timezone, timedelta
from collections import defaultdict

logger = logging.getLogger(__name__)

INDUSTRY_THRESHOLDS = {
    "cruise":        {"queue": 50,  "processing": 300, "throughput": 10},
    "healthcare":    {"queue": 20,  "processing": 3600, "throughput": 5},
    "banking":       {"queue": 100, "processing": 600, "throughput": 5},
    "ecommerce":     {"queue": 200, "processing": 180, "throughput": 50},
    "airport":       {"queue": 80,  "processing": 600, "throughput": 8},
    "construction":  {"queue": 4,   "processing": 14400, "throughput": 2},
    "civil":         {"queue": 8,   "processing": 480, "throughput": 2},
    "architecture":  {"queue": 10,  "processing": 720, "throughput": 1},
    "energy":        {"queue": 20,  "processing": 300, "throughput": 5},
    "water":         {"queue": 15,  "processing": 600, "throughput": 3},
    "weather":       {"queue": 30,  "processing": 900, "throughput": 2},
}

DAY_NAMES = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]

INDUSTRY_AI_CONTEXT = {
    "construction": "A project-management-oriented construction workflow involving permits, inspections, subcontractor coordination, and handoff risk.",
}

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "check_health_scores",
            "description": "Check current health scores for all stages. Always call this first.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_open_incidents",
            "description": "Get all currently open incidents with their IDs and severity.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_cascade_predictions",
            "description": "Check for active cascade risks between stages.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_eta_to_breach",
            "description": "Get ETA to breach for all declining stages based on health trajectory.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_recurring_patterns",
            "description": "Get recurring failure patterns for a specific stage name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "stage_name": {
                        "type": "string",
                        "description": "The exact stage name e.g. security_check, permits_approvals",
                    }
                },
                "required": ["stage_name"],
            },
        },
    },
]


def execute_tool(tool_name: str, tool_args: dict, supabase: Client, groq_api_key: str, industry: str) -> str:
    thresholds = INDUSTRY_THRESHOLDS.get(industry, {"queue": 50, "processing": 300, "throughput": 10})

    try:
        if tool_name == "check_health_scores":
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
            response = supabase.table("workflow_metrics").select("stage, health_score, recorded_at").eq("industry", industry).gte("recorded_at", cutoff).order("recorded_at", desc=True).execute()
            stage_readings: dict = defaultdict(list)
            for row in (response.data or []):
                stage_readings[row["stage"]].append(row["health_score"])
            if not stage_readings:
                return "No health data available for this industry."
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
            return "Current health scores:\n" + "\n".join(results)

        elif tool_name == "get_open_incidents":
            response = supabase.table("incidents").select("id, stage, severity, description, created_at").eq("industry", industry).eq("status", "open").order("created_at", desc=True).execute()
            if not response.data:
                return "No open incidents."
            results = [f"- [{i['severity'].upper()}] {i['stage']}: {i['description']} (id: {i['id'][:8]}...)" for i in response.data]
            return f"Open incidents ({len(response.data)}):\n" + "\n".join(results)

        elif tool_name == "get_cascade_predictions":
            cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
            response = supabase.table("workflow_metrics").select("stage, queue_size, processing_time_seconds, throughput, health_score, recorded_at").eq("industry", industry).gte("recorded_at", cutoff).order("recorded_at").execute()
            stage_buckets: dict = defaultdict(dict)
            for row in (response.data or []):
                ts = datetime.fromisoformat(row["recorded_at"].replace("Z", "+00:00"))
                bucket_key = ts.replace(minute=0, second=0, microsecond=0).isoformat()
                breached = row["queue_size"] > thresholds["queue"] or row["processing_time_seconds"] > thresholds["processing"] or row["throughput"] < thresholds["throughput"]
                stage_buckets[row["stage"]][bucket_key] = {"health": row["health_score"], "breached": breached}
            stages = list(stage_buckets.keys())
            active_risks = []
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
                    currently_stressed = any(source_data[k]["breached"] for k in recent_source)
                    if currently_stressed and confidence >= 60:
                        active_risks.append(f"ACTIVE RISK: {source} -> {target} ({confidence}% confidence, 2hr lag)")
            return "Active cascade risks:\n" + "\n".join(active_risks) if active_risks else "No active cascade risks detected."

        elif tool_name == "get_eta_to_breach":
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=12)).isoformat()
            response = supabase.table("workflow_metrics").select("stage, health_score, queue_size, processing_time_seconds, throughput, recorded_at").eq("industry", industry).gte("recorded_at", cutoff).order("recorded_at", desc=True).execute()
            stage_readings2: dict = defaultdict(list)
            for row in (response.data or []):
                stage_readings2[row["stage"]].append(row)
            results = []
            for stage, readings in stage_readings2.items():
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
                hcph = slope / 2
                already_breached = (
                    readings[0]["queue_size"] > thresholds["queue"] or
                    readings[0]["processing_time_seconds"] > thresholds["processing"] or
                    readings[0]["throughput"] < thresholds["throughput"]
                )
                if already_breached:
                    results.append(f"- {stage}: ALREADY BREACHED — immediate action required")
                elif hcph < 0 and current_health < 85:
                    hours = round((current_health - 40) / abs(hcph), 1)
                    urgency = "CRITICAL" if hours <= 2 else "WARNING" if hours <= 6 else "MONITOR"
                    results.append(f"- {stage}: {urgency} — breach in ~{hours}hrs (health: {current_health})")
            return "ETA to breach:\n" + "\n".join(results) if results else "All stages stable. No breach predicted."

        elif tool_name == "get_recurring_patterns":
            stage_name = tool_args.get("stage_name", "")
            if not stage_name:
                return "Please provide a stage_name."
            cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
            response = supabase.table("workflow_metrics").select("queue_size, processing_time_seconds, throughput, recorded_at").eq("industry", industry).eq("stage", stage_name).gte("recorded_at", cutoff).execute()
            if not response.data:
                return f"No data found for stage '{stage_name}'."
            breaches = []
            for row in response.data:
                if row["queue_size"] > thresholds["queue"] or row["processing_time_seconds"] > thresholds["processing"] or row["throughput"] < thresholds["throughput"]:
                    ts = datetime.fromisoformat(row["recorded_at"].replace("Z", "+00:00"))
                    breaches.append({"hour": ts.hour, "dow": int(ts.strftime("%w"))})
            if not breaches:
                return f"Stage '{stage_name}' has no threshold breaches in the last 30 days."
            hour_counts: dict = defaultdict(int)
            dow_counts: dict = defaultdict(int)
            for b in breaches:
                hour_counts[b["hour"]] += 1
                dow_counts[b["dow"]] += 1
            peak_hour = max(hour_counts, key=lambda h: hour_counts[h])
            peak_dow = max(dow_counts, key=lambda d: dow_counts[d])
            hour_label = f"{'12' if peak_hour == 12 else peak_hour % 12 or 12}{'am' if peak_hour < 12 else 'pm'}"
            return (
                f"Stage '{stage_name}': {len(breaches)} breaches in 30 days. "
                f"Peak time: {hour_label} ({round(hour_counts[peak_hour]/len(breaches)*100)}%). "
                f"Peak day: {DAY_NAMES[peak_dow]}s ({round(dow_counts[peak_dow]/len(breaches)*100)}%). "
                f"Severity: {'high' if len(breaches) > 20 else 'medium' if len(breaches) > 10 else 'low'}."
            )

        else:
            return f"Unknown tool: {tool_name}"

    except Exception as e:
        return f"Tool '{tool_name}' error: {str(e)}"


def run_investigation(supabase: Client, groq_api_key: str, industry: str, custom_goal: str = "") -> dict:
    goal = custom_goal or f"Investigate the {industry} operation. Check health scores, open incidents, cascade risks, ETAs, and patterns for any critical stages. Provide a prioritized action plan."
    if not groq_api_key:
        logger.error("Agent investigation requested without GROQ_API_KEY for industry=%s", industry)
        return {
            "success": False,
            "error": "AI provider is not configured on the backend. Set GROQ_API_KEY on Render.",
            "reason": "backend",
            "industry": industry,
            "steps": [],
            "output": "",
            "decision_points": [],
            "investigated_at": datetime.now(timezone.utc).isoformat(),
        }

    system_prompt = f"""You are an AI operations intelligence agent for a {industry} operation.
Industry context: {INDUSTRY_AI_CONTEXT.get(industry, f"A workflow-driven {industry} operation.")}
Investigate systematically:
1. Call check_health_scores first
2. Call get_open_incidents
3. Call get_cascade_predictions
4. Call get_eta_to_breach
5. For any critical or severe stage, call get_recurring_patterns with that stage name
6. Write a structured report:
   CRITICAL ISSUES: stages/incidents needing immediate action
   WARNING ISSUES: stages trending bad
   RECOMMENDED ACTIONS: numbered list, most urgent first
Use actual stage names and numbers. Be specific.
For construction, emphasize permit delays, inspection backlog, blocked downstream work, subcontractor coordination, and handover risk."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": goal},
    ]

    parsed_steps = []
    max_iterations = 4
    total_runtime_seconds = 40
    per_call_timeout_seconds = 25.0
    iteration = 0
    output = "Investigation complete."
    started_at = time.monotonic()

    try:
        with httpx.Client(timeout=per_call_timeout_seconds) as client:
            while iteration < max_iterations:
                iteration += 1
                if time.monotonic() - started_at >= total_runtime_seconds:
                    logger.warning("Agent investigation exceeded runtime budget for %s", industry)
                    return {
                        "success": False,
                        "error": "Investigation timed out before the backend could finish.",
                        "reason": "timeout",
                        "industry": industry,
                        "steps": parsed_steps,
                        "output": "",
                        "decision_points": [],
                        "investigated_at": datetime.now(timezone.utc).isoformat(),
                    }

                response = client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {groq_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "llama-3.3-70b-versatile",
                        "messages": messages,
                        "tools": TOOLS,
                        "tool_choice": "auto",
                        "max_tokens": 1500,
                    },
                )

                if response.status_code == 429:
                    logger.warning("Agent investigation rate limited for %s", industry)
                    return {"success": False, "error": "Rate limited by model provider.", "reason": "rate_limit", "industry": industry, "steps": parsed_steps, "output": "", "decision_points": [], "investigated_at": datetime.now(timezone.utc).isoformat()}
                if response.status_code in {401, 403}:
                    logger.error("Agent investigation Groq authentication failed for %s with status %s", industry, response.status_code)
                    return {"success": False, "error": "AI provider authentication failed. Verify GROQ_API_KEY on Render.", "reason": "backend", "industry": industry, "steps": parsed_steps, "output": "", "decision_points": [], "investigated_at": datetime.now(timezone.utc).isoformat()}

                response.raise_for_status()
                data = response.json()
                if not isinstance(data, dict):
                    logger.error("Agent investigation received non-dict response for %s: %r", industry, data)
                    return {"success": False, "error": "AI provider returned an invalid response.", "reason": "backend", "industry": industry, "steps": parsed_steps, "output": "", "decision_points": [], "investigated_at": datetime.now(timezone.utc).isoformat()}

                choices = data.get("choices") or []
                if not choices:
                    output = "Agent received an empty response. Please try again."
                    break

                choice = choices[0] or {}
                if not isinstance(choice, dict):
                    logger.error("Agent investigation received invalid choice for %s: %r", industry, choice)
                    return {"success": False, "error": "AI provider returned an invalid choice payload.", "reason": "backend", "industry": industry, "steps": parsed_steps, "output": "", "decision_points": [], "investigated_at": datetime.now(timezone.utc).isoformat()}
                message = choice.get("message") or {}
                if not isinstance(message, dict):
                    logger.error("Agent investigation received invalid message for %s: %r", industry, message)
                    return {"success": False, "error": "AI provider returned an invalid message payload.", "reason": "backend", "industry": industry, "steps": parsed_steps, "output": "", "decision_points": [], "investigated_at": datetime.now(timezone.utc).isoformat()}
                messages.append(message)

                tool_calls = message.get("tool_calls") or []
                if not tool_calls:
                    output = message.get("content") or "Investigation complete."
                    break

                for tool_call in tool_calls:
                    if not isinstance(tool_call, dict):
                        logger.warning("Skipping invalid tool call for %s: %r", industry, tool_call)
                        continue
                    fn = tool_call.get("function") or {}
                    if not isinstance(fn, dict):
                        logger.warning("Skipping invalid function payload for %s: %r", industry, fn)
                        continue
                    tool_name = fn.get("name", "")
                    try:
                        tool_args = json.loads(fn.get("arguments") or "{}")
                    except (json.JSONDecodeError, TypeError):
                        tool_args = {}

                    finding = execute_tool(tool_name, tool_args, supabase, groq_api_key, industry)

                    parsed_steps.append({
                        "step": len(parsed_steps) + 1,
                        "tool": tool_name,
                        "input": str(tool_args.get("stage_name", tool_args.get("incident_id", ""))),
                        "finding": str(finding)[:500],
                    })

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.get("id", ""),
                        "content": str(finding),
                    })

            else:
                output = "Investigation reached maximum iterations."

    except httpx.TimeoutException:
        logger.warning("Agent investigation request timed out for %s", industry)
        return {"success": False, "error": "Investigation timed out.", "reason": "timeout", "industry": industry, "steps": parsed_steps, "output": "", "decision_points": [], "investigated_at": datetime.now(timezone.utc).isoformat()}
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code if exc.response else 502
        logger.exception("Agent investigation provider HTTP error for %s with status %s", industry, status_code)
        return {"success": False, "error": f"AI provider request failed with status {status_code}.", "reason": "backend", "industry": industry, "steps": parsed_steps, "output": "", "decision_points": [], "investigated_at": datetime.now(timezone.utc).isoformat()}
    except Exception as e:
        logger.exception("Agent investigation failed for %s", industry)
        return {"success": False, "error": "Backend investigation failed.", "reason": "backend", "industry": industry, "steps": parsed_steps, "output": "", "decision_points": [], "investigated_at": datetime.now(timezone.utc).isoformat()}

    output_lower = output.lower()
    decision_points = []

    if any(w in output_lower for w in ["critical", "severe", "breached", "immediate"]):
        decision_points.append({"id": "acknowledge_critical", "type": "acknowledge", "question": "The agent found critical issues. Do you want to acknowledge these and flag them for the ops team?", "action": "trigger_alerts"})

    if any(w in output_lower for w in ["recurring", "pattern", "breaches in 30"]):
        decision_points.append({"id": "generate_playbook", "type": "playbook", "question": "Recurring failure patterns were detected. Do you want to auto-generate playbooks for affected stages?", "action": "generate_playbooks"})

    if "cascade" in output_lower:
        decision_points.append({"id": "cascade_alert", "type": "alert", "question": "A cascade risk was detected. Do you want to note this for the ops team?", "action": "send_cascade_alert"})

    decision_points.append({"id": "log_investigation", "type": "audit", "question": "Log this investigation to the audit trail?", "action": "log_audit"})

    return {"success": True, "industry": industry, "goal": goal, "steps": parsed_steps, "output": output, "decision_points": decision_points, "investigated_at": datetime.now(timezone.utc).isoformat()}
