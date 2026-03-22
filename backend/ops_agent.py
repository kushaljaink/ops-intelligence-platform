"""
ops_agent.py — AI Agent using Groq's native tool-calling API directly.
No LangChain needed. Groq supports OpenAI-compatible function calling.
"""

import httpx
import json
from supabase import Client
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from typing import Optional

INDUSTRY_THRESHOLDS = {
    "cruise":     {"queue": 50,  "processing": 300, "throughput": 10},
    "healthcare": {"queue": 20,  "processing": 120, "throughput": 15},
    "banking":    {"queue": 100, "processing": 600, "throughput": 5},
    "ecommerce":  {"queue": 200, "processing": 180, "throughput": 50},
    "airport":    {"queue": 80,  "processing": 240, "throughput": 20},
}

DAY_NAMES = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]

# Tool definitions for Groq function calling
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
            "description": "Get all currently open incidents.",
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
            "description": "Get ETA to breach for all declining stages.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_recurring_patterns",
            "description": "Get recurring failure patterns for a specific stage.",
            "parameters": {
                "type": "object",
                "properties": {
                    "stage_name": {
                        "type": "string",
                        "description": "The stage name e.g. security_check",
                    }
                },
                "required": ["stage_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_open_incidents",
            "description": "Get list of open incidents with IDs.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]


def execute_tool(tool_name: str, tool_args: dict, supabase: Client, groq_api_key: str, industry: str) -> str:
    thresholds = INDUSTRY_THRESHOLDS.get(industry, {"queue": 50, "processing": 300, "throughput": 10})

    if tool_name == "check_health_scores":
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        response = supabase.table("workflow_metrics").select("stage, health_score, recorded_at").eq("industry", industry).gte("recorded_at", cutoff).order("recorded_at", desc=True).execute()
        stage_readings: dict = defaultdict(list)
        for row in response.data:
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
        for row in response.data:
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
        for row in response.data:
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
            already_breached = readings[0]["queue_size"] > thresholds["queue"] or readings[0]["processing_time_seconds"] > thresholds["processing"] or readings[0]["throughput"] < thresholds["throughput"]
            if already_breached:
                results.append(f"- {stage}: ALREADY BREACHED")
            elif hcph < 0 and current_health < 85:
                hours = round((current_health - 40) / abs(hcph), 1)
                urgency = "CRITICAL" if hours <= 2 else "WARNING" if hours <= 6 else "MONITOR"
                results.append(f"- {stage}: {urgency} breach in ~{hours}hrs (health: {current_health})")
        return "ETA to breach:\n" + "\n".join(results) if results else "All stages stable. No breach predicted."

    elif tool_name == "get_recurring_patterns":
        stage_name = tool_args.get("stage_name", "")
        cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        response = supabase.table("workflow_metrics").select("queue_size, processing_time_seconds, throughput, recorded_at").eq("industry", industry).eq("stage", stage_name).gte("recorded_at", cutoff).execute()
        if not response.data:
            return f"No data for '{stage_name}'."
        breaches = []
        for row in response.data:
            if row["queue_size"] > thresholds["queue"] or row["processing_time_seconds"] > thresholds["processing"] or row["throughput"] < thresholds["throughput"]:
                ts = datetime.fromisoformat(row["recorded_at"].replace("Z", "+00:00"))
                breaches.append({"hour": ts.hour, "dow": int(ts.strftime("%w"))})
        if not breaches:
            return f"'{stage_name}' has no breaches in 30 days."
        hour_counts: dict = defaultdict(int)
        dow_counts: dict = defaultdict(int)
        for b in breaches:
            hour_counts[b["hour"]] += 1
            dow_counts[b["dow"]] += 1
        peak_hour = max(hour_counts, key=lambda h: hour_counts[h])
        peak_dow = max(dow_counts, key=lambda d: dow_counts[d])
        hour_label = f"{'12' if peak_hour == 12 else peak_hour % 12 or 12}{'am' if peak_hour < 12 else 'pm'}"
        return (f"'{stage_name}': {len(breaches)} breaches in 30 days. "
                f"Peak: {hour_label} ({round(hour_counts[peak_hour]/len(breaches)*100)}%). "
                f"Peak day: {DAY_NAMES[peak_dow]}s ({round(dow_counts[peak_dow]/len(breaches)*100)}%).")

    return f"Unknown tool: {tool_name}"


def run_investigation(supabase: Client, groq_api_key: str, industry: str, custom_goal: str = "") -> dict:
    goal = custom_goal or f"Investigate the {industry} operation. Check health, incidents, cascades, ETAs, and patterns. Give a prioritized action plan."

    system_prompt = f"""You are an AI operations intelligence agent for a {industry} operation.
Investigate systematically using the available tools.
Start with check_health_scores, then get_open_incidents, then get_cascade_predictions.
For any critical/severe stage, call get_recurring_patterns with that stage name.
Then call get_eta_to_breach.
After gathering data, write a structured report with: CRITICAL ISSUES, WARNING ISSUES, RECOMMENDED ACTIONS.
Use actual numbers and stage names. Be specific and urgent."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": goal},
    ]

    parsed_steps = []
    max_iterations = 8
    iteration = 0

    with httpx.Client(timeout=60.0) as client:
        while iteration < max_iterations:
            iteration += 1

            response = client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {groq_api_key}", "Content-Type": "application/json"},
                json={
                    "model": "llama-3.3-70b-versatile",
                    "messages": messages,
                    "tools": TOOLS,
                    "tool_choice": "auto",
                    "max_tokens": 1000,
                },
            )

            if response.status_code == 429:
                return {"success": False, "error": "GROQ_RATE_LIMIT: Rate limited. Wait 60 seconds.", "steps": [], "output": "", "decision_points": []}

            response.raise_for_status()
            data = response.json()
            choice = data["choices"][0]
            message = choice["message"]

            # Add assistant message to history
            messages.append(message)

            # If no tool calls, agent is done
            if not message.get("tool_calls"):
                output = message.get("content", "Investigation complete.")
                break

            # Execute each tool call
            for tool_call in message["tool_calls"]:
                tool_name = tool_call["function"]["name"]
                try:
                    tool_args = json.loads(tool_call["function"]["arguments"] or "{}")
                except json.JSONDecodeError:
                    tool_args = {}

                finding = execute_tool(tool_name, tool_args, supabase, groq_api_key, industry)

                parsed_steps.append({
                    "step": len(parsed_steps) + 1,
                    "tool": tool_name,
                    "input": str(tool_args.get("stage_name", tool_args.get("incident_id", ""))),
                    "finding": finding[:500],
                })

                # Add tool result to messages
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": finding,
                })
        else:
            output = "Investigation reached maximum iterations."

    output_lower = output.lower()
    decision_points = []
    if "critical" in output_lower or "severe" in output_lower or "breached" in output_lower:
        decision_points.append({"id": "acknowledge_critical", "type": "acknowledge", "question": "The agent found critical issues. Do you want to acknowledge these and flag them for the ops team?", "action": "trigger_alerts"})
    if "recurring" in output_lower or "pattern" in output_lower:
        decision_points.append({"id": "generate_playbook", "type": "playbook", "question": "Recurring failure patterns were detected. Do you want to auto-generate playbooks for affected stages?", "action": "generate_playbooks"})
    if "cascade" in output_lower:
        decision_points.append({"id": "cascade_alert", "type": "alert", "question": "A cascade risk was detected. Do you want to note this for the ops team?", "action": "send_cascade_alert"})
    decision_points.append({"id": "log_investigation", "type": "audit", "question": "Log this investigation to the audit trail?", "action": "log_audit"})

    return {
        "success": True,
        "industry": industry,
        "goal": goal,
        "steps": parsed_steps,
        "output": output,
        "decision_points": decision_points,
        "investigated_at": datetime.now(timezone.utc).isoformat(),
    }
