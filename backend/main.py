from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import List
import os
import httpx
from supabase import create_client

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

@app.get("/health")
def health():
    return {"status": "ok", "service": "Ops Intelligence Platform"}

@app.get("/incidents")
def get_incidents():
    response = supabase.table("incidents").select("*").order("created_at", desc=True).execute()
    return {"incidents": response.data}

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
    prompt = (
        f"Analyze this operational incident and provide a concise root cause analysis and recommended remediation steps.\n\n"
        f"Title: {incident.get('title', 'N/A')}\n"
        f"Severity: {incident.get('severity', 'N/A')}\n"
        f"Status: {incident.get('status', 'N/A')}\n"
        f"Description: {incident.get('description', 'N/A')}\n"
        f"Service: {incident.get('service', 'N/A')}\n"
    )

    async with httpx.AsyncClient(timeout=30.0) as client:
        groq_response = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        groq_response.raise_for_status()

    analysis = groq_response.json()["choices"][0]["message"]["content"]
    return {
        "incident_id": incident_id,
        "stage": incident.get("stage"),
        "severity": incident.get("severity"),
        "ai_analysis": analysis,
    }


class WorkflowRow(BaseModel):
    stage: str
    queue_size: float
    processing_time_seconds: float
    throughput: float

class AnalyzeCustomRequest(BaseModel):
    rows: List[WorkflowRow]

@app.post("/analyze-custom")
async def analyze_custom(body: AnalyzeCustomRequest):
    rows = body.rows
    if not rows:
        raise HTTPException(status_code=400, detail="No workflow data provided")

    # Rules engine
    issues = []
    for r in rows:
        row_issues = []
        if r.queue_size > 50:
            row_issues.append(f"queue backed up ({r.queue_size} items)")
        if r.processing_time_seconds > 300:
            row_issues.append(f"processing time too high ({r.processing_time_seconds}s)")
        if r.throughput < 10:
            row_issues.append(f"throughput critically low ({r.throughput}/hr)")
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
        "You are an operations analyst. Analyze the following workflow metrics and provide:\n"
        "1. A brief assessment of the overall operational health\n"
        "2. Specific bottlenecks or risks identified\n"
        "3. Concrete recommended actions for the operations team\n\n"
        f"Workflow data:\n{rows_text}\n\n"
        f"Rule-based issues detected:\n{issues_text}\n\n"
        "Be concise and practical. Focus on actionable next steps."
    )

    async with httpx.AsyncClient(timeout=30.0) as client:
        groq_response = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        groq_response.raise_for_status()

    ai_analysis = groq_response.json()["choices"][0]["message"]["content"]
    return {
        "detected_issues": issues,
        "ai_analysis": ai_analysis,
    }
