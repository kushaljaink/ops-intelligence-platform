"""
ops_agent.py — Human-in-the-Loop AI Agent for Ops Intelligence Platform

Architecture:
- LangChain agent with Groq (llama-3.3-70b) as the reasoning engine
- 6 tools the agent can call to investigate operational state
- Human-in-the-loop: agent pauses at every consequential action
- Investigation steps are streamed back to the frontend in real time
"""

from langchain_groq import ChatGroq
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage
from langchain.agents import AgentExecutor, create_tool_calling_agent
from supabase import Client
from datetime import datetime, timezone, timedelta
from collections import defaultdict
import os
import httpx

INDUSTRY_THRESHOLDS = {
    "cruise":     {"queue": 50,  "processing": 300, "throughput": 10},
    "healthcare": {"queue": 20,  "processing": 120, "throughput": 15},
    "banking":    {"queue": 100, "processing": 600, "throughput": 5},
    "ecommerce":  {"queue": 200, "processing": 180, "throughput": 50},
    "airport":    {"queue": 80,  "processing": 240, "throughput": 20},
}


def build_agent_tools(supabase: Client, groq_api_key: str, industry: str):
    """
    Build the agent's toolset bound to a specific industry and supabase instance.
    Tools are plain functions decorated with @tool — the agent decides when to call them.
    """

    @tool
    def check_health_scores(dummy: str = "") -> str:
        """Check current health scores for all stages in the operation. Returns health score, trend, and status for each stage."""
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        response = supabase.table("workflow_metrics").select("stage, health_score, recorded_at").eq("industry", industry).gte("recorded_at", cutoff).order("recorded_at", desc=True).execute()
        stage_readings: dict = defaultdict(list)
        for row in response.data:
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

    @tool
    def get_cascade_predictions(dummy: str = "") -> str:
        """Check for cascade relationships between stages. Returns any active cascade risks where one stage failing causes another to degrade."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        thresholds = INDUSTRY_THRESHOLDS.get(industry, {"queue": 50, "processing": 300, "throughput": 10})
        response = supabase.table("workflow_metrics").select("stage, queue_size, processing_time_seconds, throughput, health_score, recorded_at").eq("industry", industry).gte("recorded_at", cutoff).order("recorded_at").execute()
        stage_buckets: dict = defaultdict(dict)
        for row in response.data:
            from datetime import datetime
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
                    active_risks.append(f"ACTIVE RISK: {source} → {target} ({confidence}% confidence, 2hr lag)")
        if not active_risks:
            return "No active cascade risks detected."
        return "Active cascade risks:\n" + "\n".join(active_risks)

    @tool
    def get_recurring_patterns(stage_name: str) -> str:
        """Get recurring failure patterns for a specific stage. Input: stage name (e.g. 'security_check'). Returns how often it fails, peak times, and peak days."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        thresholds = INDUSTRY_THRESHOLDS.get(industry, {"queue": 50, "processing": 300, "throughput": 10})
        response = supabase.table("workflow_metrics").select("queue_size, processing_time_seconds, throughput, health_score, recorded_at").eq("industry", industry).eq("stage", stage_name).gte("recorded_at", cutoff).execute()
        if not response.data:
            return f"No data found for stage '{stage_name}'."
        breaches = []
        DAY_NAMES = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
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
        peak_hour_pct = round(hour_counts[peak_hour] / len(breaches) * 100)
        peak_dow_pct = round(dow_counts[peak_dow] / len(breaches) * 100)
        return (
            f"Stage '{stage_name}' patterns:\n"
            f"- Total breaches in 30 days: {len(breaches)}\n"
            f"- Peak time: {hour_label} ({peak_hour_pct}% of failures)\n"
            f"- Peak day: {DAY_NAMES[peak_dow]}s ({peak_dow_pct}% of failures)\n"
            f"- Severity: {'high' if len(breaches) > 20 else 'medium' if len(breaches) > 10 else 'low'}"
        )

    @tool
    def get_eta_to_breach(dummy: str = "") -> str:
        """Calculate ETA to breach for all declining stages based on health score trajectory. Returns urgency and estimated hours to critical threshold."""
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
                hours_to_critical = (current_health - 40) / abs(health_change_per_hour)
                eta = round(hours_to_critical, 1)
                urgency = "CRITICAL" if eta <= 2 else "WARNING" if eta <= 6 else "MONITOR"
                results.append(f"- {stage}: {urgency} — breach in ~{eta}hrs (current health: {current_health})")
        if not results:
            return "All stages are stable or improving. No breach predicted."
        return "ETA to breach:\n" + "\n".join(results)

    @tool
    def get_open_incidents(dummy: str = "") -> str:
        """Get all currently open incidents for this industry. Returns stage, severity, and description of each open incident."""
        response = supabase.table("incidents").select("id, stage, severity, description, created_at").eq("industry", industry).eq("status", "open").order("created_at", desc=True).execute()
        if not response.data:
            return "No open incidents."
        results = []
        for inc in response.data:
            results.append(f"- [{inc['severity'].upper()}] {inc['stage']}: {inc['description']} (id: {inc['id'][:8]}...)")
        return f"Open incidents ({len(response.data)}):\n" + "\n".join(results)

    @tool
    def analyze_specific_incident(incident_id: str) -> str:
        """Run AI analysis on a specific incident by its ID. Input: full incident UUID. Returns root cause and recommendations."""
        result = supabase.table("incidents").select("*").eq("id", incident_id).single().execute()
        if not result.data:
            return f"Incident {incident_id} not found."
        incident = result.data
        prompt = (
            f"Senior ops analyst. {industry} operation.\n"
            f"Stage: {incident.get('stage')} | Severity: {incident.get('severity')}\n"
            f"Description: {incident.get('description')}\n"
            "Give: 1) Root cause 2) Downstream impact 3) 3 immediate actions. Be specific."
        )
        import httpx
        response = httpx.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {groq_api_key}"},
            json={"model": "llama-3.3-70b-versatile", "messages": [{"role": "user", "content": prompt}], "max_tokens": 400},
            timeout=30.0,
        )
        if response.status_code != 200:
            return f"Analysis failed: HTTP {response.status_code}"
        analysis = response.json()["choices"][0]["message"]["content"]
        supabase.table("analysis_logs").insert({"incident_id": incident_id, "ai_analysis": analysis, "triggered_by": "agent"}).execute()
        return f"Analysis for {incident.get('stage')}:\n{analysis}"

    return [
        check_health_scores,
        get_cascade_predictions,
        get_recurring_patterns,
        get_eta_to_breach,
        get_open_incidents,
        analyze_specific_incident,
    ]


def build_agent(supabase: Client, groq_api_key: str, industry: str) -> AgentExecutor:
    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        api_key=groq_api_key,
        temperature=0,
        max_tokens=1000,
    )
    tools = build_agent_tools(supabase, groq_api_key, industry)

    prompt = ChatPromptTemplate.from_messages([
        ("system", f"""You are an AI operations intelligence agent investigating a {industry} operation.
Check health scores first, then cascade risks and open incidents.
For any critical or severe stage, check its recurring patterns and ETA to breach.
Prioritize findings by urgency. End with a structured action list for the ops team.
Use actual numbers and stage names. Be specific."""),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])

    agent = create_tool_calling_agent(llm, tools, prompt)
    return AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        max_iterations=8,
        return_intermediate_steps=True,
        handle_parsing_errors=True,
    )


def run_investigation(supabase: Client, groq_api_key: str, industry: str, custom_goal: str = "") -> dict:
    """
    Run a full agent investigation and return structured results.
    Returns: steps taken, findings, and recommended human decisions.
    """
    agent_executor = build_agent(supabase, groq_api_key, industry)

    goal = custom_goal or f"Investigate the current operational state of the {industry} operation. Identify the most critical issues, check for cascade risks and patterns, and provide a prioritized action plan for the ops team."

    try:
        result = agent_executor.invoke({"input": goal})
        output = result.get("output", "")
        steps = result.get("intermediate_steps", [])

        # Parse steps into readable format
        parsed_steps = []
        for i, (action, observation) in enumerate(steps):
            parsed_steps.append({
                "step": i + 1,
                "tool": action.tool,
                "input": action.tool_input if isinstance(action.tool_input, str) else str(action.tool_input),
                "finding": str(observation)[:500],
            })

        # Extract human decision points from the output
        decision_points = []

        # Look for critical/severe issues mentioned in output
        output_lower = output.lower()
        if "critical" in output_lower or "severe" in output_lower or "breached" in output_lower:
            decision_points.append({
                "id": "acknowledge_critical",
                "type": "acknowledge",
                "question": "The agent found critical issues. Do you want to mark these incidents as acknowledged and trigger alerts?",
                "action": "trigger_alerts",
            })

        if "playbook" in output_lower or "recurring" in output_lower or "pattern" in output_lower:
            # Extract stage names mentioned near "playbook" or "recurring"
            decision_points.append({
                "id": "generate_playbook",
                "type": "playbook",
                "question": "The agent identified recurring failure patterns. Do you want to auto-generate playbooks for the affected stages?",
                "action": "generate_playbooks",
            })

        if "cascade" in output_lower:
            decision_points.append({
                "id": "cascade_alert",
                "type": "alert",
                "question": "A cascade risk was detected. Do you want to send an alert to the ops team?",
                "action": "send_cascade_alert",
            })

        decision_points.append({
            "id": "log_investigation",
            "type": "audit",
            "question": "Log this investigation to the audit trail?",
            "action": "log_audit",
        })

        return {
            "success": True,
            "industry": industry,
            "goal": goal,
            "steps": parsed_steps,
            "output": output,
            "decision_points": decision_points,
            "investigated_at": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "industry": industry,
            "steps": [],
            "output": "",
            "decision_points": [],
        }
