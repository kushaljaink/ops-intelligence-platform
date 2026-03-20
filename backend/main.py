from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os
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
