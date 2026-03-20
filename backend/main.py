from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os
import httpx
from supabase import create_client

load_dotenv()

app = FastAPI(title="Ops Intelligence Platform")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

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

    async with httpx.AsyncClient(timeout=120.0) as client:
        ollama_response = await client.post(
            "http://localhost:11434/api/generate",
            json={"model": "llama3.2", "prompt": prompt, "stream": False},
        )
        ollama_response.raise_for_status()

    analysis = ollama_response.json().get("response", "")
    return {"incident_id": incident_id, "analysis": analysis}
