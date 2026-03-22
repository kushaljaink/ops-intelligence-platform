from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import StructuredTool
from langchain.agents import AgentExecutor, create_tool_calling_agent
from pydantic import BaseModel, Field
from supabase import Client
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from typing import Optional
import httpx

INDUSTRY_THRESHOLDS = {
    "cruise":     {"queue": 50,  "processing": 300, "throughput": 10},
    "healthcare": {"queue": 20,  "processing": 120, "throughput": 15},
    "banking":    {"queue": 100, "processing": 600, "throughput": 5},
    "ecommerce":  {"queue": 200, "processing": 180, "throughput": 50},
    "airport":    {"queue": 80,  "processing": 240, "throughput": 20},
}

DAY_NAMES = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]


class EmptyInput(BaseModel):
    dummy: Optional[str] = Field(default="", description="No input needed")

class StageInput(BaseModel):
    stage_name: str = Field(description="The name of the stage to analyze, e.g. security_check")

class IncidentInput(BaseModel):
    incident_id: str = Field(description="The full UUID of the incident to analyze")


def build_agent_tools(supabase: Client, groq_api_key: str, industry: str):

    def check_health_scores(dummy: str = "") -> str:
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

    def get_open_incidents(dummy: str = "") -> str:
        response = supabase.table("incidents").select("id, stage, severity, description, created_at").eq("industry", industry).eq("status", "open").order("created_at", desc=True).execute()
        if not response.data:
            return "No open incidents."
        results = [f"- [{i['severity'].upper()}] {i['stage']}: {i['description']} (id: {i['id'][:8]}...)" for i in response.data]
        return f"Open incidents ({len(response.data)}):\n" + "\n".join(results)

    def get_cascade_predictions(dummy: str = "") -> str:
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
        return "Active cascade risks:\n" + "\n".join(active_risks) if active_risks else "No active cascade risks."

    def get_recurring_patterns(stage_name: str) -> str:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        thresholds = INDUSTRY_THRESHOLDS.get(industry, {"queue": 50, "processing": 300, "throughput": 10})
        response = supabase.table("workflow_metrics").select("queue_size, processing_time_seconds, throughput, recorded_at").eq("industry", industry).eq("stage", stage_name).gte("recorded_at", cutoff).execute()
        if not response.data:
            return f"No data for stage '{stage_name}'."
        breaches = []
        for row in response.data:
            if row["queue_size"] > thresholds["queue"] or row["processing_time_seconds"] > thresholds["processing"] or row["throughput"] < thresholds["throughput"]:
                ts = datetime.fromisoformat(row["recorded_at"].replace("Z", "+00:00"))
                breaches.append({"hour": ts.hour, "dow": int(ts.strftime("%w"))})
        if not breaches:
            return f"Stage '{stage_name}' has no threshold breaches in 30 days."
        hour_counts: dict = defaultdict(int)
        dow_counts: dict = defaultdict(int)
        for b in breaches:
            hour_counts[b["hour"]] += 1
            dow_counts[b["dow"]] += 1
        peak_hour = max(hour_counts, key=lambda h: hour_counts[h])
        peak_dow = max(dow_counts, key=lambda d: dow_counts[d])
        hour_label = f"{'12' if peak_hour == 12 else peak_hour % 12 or 12}{'am' if peak_hour < 12 else 'pm'}"
        peak_hour_pct = round(hour_counts[peak_hour] / len(breaches) * 100)
        peak_dow_pct = round(dow_counts[peak_dow] / len(breaches) * 100)
        return (f"Stage '{stage_name}': {len(breaches)} breaches in 30 days. "
                f"Peak time: {hour_label} ({peak_hour_pct}%). "
                f"Peak day: {DAY_NAMES[peak_dow]}s ({peak_dow_pct}%). "
                f"Severity: {'high' if len(breaches) > 20 else 'medium' if len(breaches) > 10 else 'low'}")

    def get_eta_to_breach(dummy: str = "") -> str:
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=12)).isoformat()
        thresholds = INDUSTRY_THRESHOLDS.get(industry, {"queue": 50, "processing": 300, "throughput": 10})
        response = supabase.table("workflow_metrics").select("stage, health_score, queue_size, processing_time_seconds, throughput, recorded_at").eq("industry", industry).gte("recorded_at", cutoff).order("recorded_at", desc=True).execute()
        stage_readings: dict = defaultdict(list)
        for row in response.data:
            stage_readings[row["stage"]].append(row)
        results = []
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
            already_breached = readings[0]["queue_size"] > thresholds["queue"] or readings[0]["processing_time_seconds"] > thresholds["processing"] or readings[0]["throughput"] < thresholds["throughput"]
            if already_breached:
                results.append(f"- {stage}: ALREADY BREACHED — immediate action required")
            elif health_change_per_hour < 0 and current_health < 85:
                hours = round((current_health - 40) / abs(health_change_per_hour), 1)
                urgency = "CRITICAL" if hours <= 2 else "WARNING" if hours <= 6 else "MONITOR"
                results.append(f"- {stage}: {urgency} — breach in ~{hours}hrs (health: {current_health})")
        return "ETA to breach:\n" + "\n".join(results) if results else "All stages stable. No breach predicted."

    def analyze_specific_incident(incident_id: str) -> str:
        result = supabase.table("incidents").select("*").eq("id", incident_id).single().execute()
        if not result.data:
            return f"Incident {incident_id} not found."
        incident = result.data
        prompt = (f"Senior ops analyst. {industry}.\nStage: {incident.get('stage')} | Severity: {incident.get('severity')}\n"
                  f"Description: {incident.get('description')}\n1. Root cause 2. Downstream impact 3. 3 immediate actions.")
        try:
            response = httpx.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {groq_api_key}"},
                json={"model": "llama-3.3-70b-versatile", "messages": [{"role": "user", "content": prompt}], "max_tokens": 400},
                timeout=30.0,
            )
            analysis = response.json()["choices"][0]["message"]["content"]
            supabase.table("analysis_logs").insert({"incident_id": incident_id, "ai_analysis": analysis, "triggered_by": "agent"}).execute()
            return f"Analysis for {incident.get('stage')}:\n{analysis}"
        except Exception as e:
            return f"Analysis failed: {str(e)}"

    return [
        StructuredTool(name="check_health_scores", description="Check current health scores for all stages. Call this first.", func=check_health_scores, args_schema=EmptyInput),
        StructuredTool(name="get_open_incidents", description="Get all currently open incidents.", func=get_open_incidents, args_schema=EmptyInput),
        StructuredTool(name="get_cascade_predictions", description="Check for active cascade risks between stages.", func=get_cascade_predictions, args_schema=EmptyInput),
        StructuredTool(name="get_eta_to_breach", description="Get ETA to breach for all declining stages.", func=get_eta_to_breach, args_schema=EmptyInput),
        StructuredTool(name="get_recurring_patterns", description="Get recurring failure patterns for a specific stage.", func=get_recurring_patterns, args_schema=StageInput),
        StructuredTool(name="analyze_specific_incident", description="Run AI analysis on a specific incident by its ID.", func=analyze_specific_incident, args_schema=IncidentInput),
    ]


def build_agent(supabase: Client, groq_api_key: str, industry: str) -> AgentExecutor:
    llm = ChatGroq(model="llama-3.3-70b-versatile", api_key=groq_api_key, temperature=0, max_tokens=1000)
    tools = build_agent_tools(supabase, groq_api_key, industry)
    prompt = ChatPromptTemplate.from_messages([
        ("system", f"""You are an AI operations intelligence agent investigating a {industry} operation.
Always start by calling check_health_scores, then get_open_incidents, then get_cascade_predictions.
For any critical or severe stage, call get_recurring_patterns with that stage name.
Then call get_eta_to_breach to see how urgent things are.
End with a structured report: CRITICAL ISSUES, WARNING ISSUES, RECOMMENDED ACTIONS."""),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])
    agent = create_tool_calling_agent(llm, tools, prompt)
    return AgentExecutor(agent=agent, tools=tools, verbose=True, max_iterations=10, return_intermediate_steps=True, handle_parsing_errors=True)


def run_investigation(supabase: Client, groq_api_key: str, industry: str, custom_goal: str = "") -> dict:
    agent_executor = build_agent(supabase, groq_api_key, industry)
    goal = custom_goal or f"Investigate the current operational state of the {industry} operation and provide a prioritized action plan."
    try:
        result = agent_executor.invoke({"input": goal})
        output = result.get("output", "")
        steps = result.get("intermediate_steps", [])
        parsed_steps = []
        for i, (action, observation) in enumerate(steps):
            parsed_steps.append({
                "step": i + 1,
                "tool": action.tool,
                "input": str(action.tool_input) if action.tool_input else "",
                "finding": str(observation)[:500],
            })
        output_lower = output.lower()
        decision_points = []
        if "critical" in output_lower or "severe" in output_lower or "breached" in output_lower:
            decision_points.append({"id": "acknowledge_critical", "type": "acknowledge", "question": "The agent found critical issues. Do you want to acknowledge these and flag them for the ops team?", "action": "trigger_alerts"})
        if "recurring" in output_lower or "pattern" in output_lower or "playbook" in output_lower:
            decision_points.append({"id": "generate_playbook", "type": "playbook", "question": "Recurring failure patterns were detected. Do you want to auto-generate playbooks for affected stages?", "action": "generate_playbooks"})
        if "cascade" in output_lower:
            decision_points.append({"id": "cascade_alert", "type": "alert", "question": "A cascade risk was detected. Do you want to note this for the ops team?", "action": "send_cascade_alert"})
        decision_points.append({"id": "log_investigation", "type": "audit", "question": "Log this investigation to the audit trail?", "action": "log_audit"})
        return {"success": True, "industry": industry, "goal": goal, "steps": parsed_steps, "output": output, "decision_points": decision_points, "investigated_at": datetime.now(timezone.utc).isoformat()}
    except Exception as e:
        return {"success": False, "error": str(e), "industry": industry, "steps": [], "output": "", "decision_points": []}
