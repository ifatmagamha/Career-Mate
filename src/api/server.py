from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Any
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import HumanMessage
import uuid
from datetime import datetime

from src.graph.build_graph import build_recruit_graph
from src.config.logging import logger
from src.api.agent_traces import router as traces_router

# Initialize FastAPI
app = FastAPI(title="Career Mate API")

# Allow CORS for React app
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(traces_router)

# Initialize Graph
graph = build_recruit_graph()

# --- Models ---
class ChatRequest(BaseModel):
    message: str
    history: Optional[List[dict]] = None

class Job(BaseModel):
    id: str
    title: str
    company: str
    location: str
    matchScore: int
    description: str

class ProfileSwitchRequest(BaseModel):
    profile_key: str

# --- Global State (MVP) ---
ACTIVE_PROFILE_KEY = "custom"

# --- Endpoints ---

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/")
def root():
    return {"message": "RecruitAI API is running. Visit /docs for Swagger UI or open the React App."}

@app.post("/api/profile/switch")
def switch_profile(req: ProfileSwitchRequest):
    # For now, we only support the single 'custom' profile in this simplified view
    return {"status": "ok", "active_profile": "custom"}

@app.get("/api/profile/current")
def get_current_profile():
    from src.data.mock_profiles import MOCK_PROFILES
    
    # Check if we have a custom uploaded profile
    profile = MOCK_PROFILES.get("custom")
    
    if not profile:
        # Return empty state if no profile uploaded yet
        return {
            "key": None,
            "name": "",
            "title": "",
            "email": "",
            "location": "",
            "skills": [],
            "summary": "",
            "experience": [] 
        }

    return {
        "key": "custom",
        "name": profile.full_name or "",
        "title": "My Profile", 
        "email": profile.email,
        "location": profile.location,
        "skills": getattr(profile, "skills", []),
        "summary": getattr(profile, "summary", ""),
        "experience": getattr(profile, "experience", [])
    }

from fastapi import UploadFile, File
from src.ingestion.resume_parser import handle_resume_upload

@app.on_event("startup")
async def startup_event():
    """Sync CVs from folder on startup."""
    from src.ingestion.resume_parser import sync_cvs_folder
    try:
        count = await sync_cvs_folder()
        logger.info(f"Startup: Synced {count} CVs from data/cvs")
    except Exception as e:
        logger.error(f"Startup sync failed: {e}")

@app.post("/api/upload_resume")
async def upload_resume(file: UploadFile = File(...)):
    """
    Parse uploaded resume and switch active profile to 'custom'.
    """
    import time
    from src.api.agent_traces import log_agent_trace
    start_time = time.time()
    try:
        global ACTIVE_PROFILE_KEY
        # 1. Process Upload
        profile, raw_data = await handle_resume_upload(file, session_id="user_123")
        
        # 2. Persist to Runtime Store (MVP)
        from src.data.mock_profiles import MOCK_PROFILES
        MOCK_PROFILES["custom"] = profile
        
        # 3. Switch Context
        ACTIVE_PROFILE_KEY = "custom"
        
        duration = (time.time() - start_time) * 1000
        log_agent_trace("Parser", f"File: {file.filename}", f"Parsed profile for {profile.full_name}", duration)
        
        return {
            "status": "success",
            "profile": raw_data,
            "message": "Resume parsed and set as active."
        }
    except Exception as e:
        duration = (time.time() - start_time) * 1000
        log_agent_trace("Parser", f"File: {file.filename}", str(e), duration, status="error")
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/profile/sync")
async def sync_profile_folder():
    """Trigger manual sync from data/cvs folder."""
    from src.ingestion.resume_parser import sync_cvs_folder
    count = await sync_cvs_folder()
    return {"status": "success", "count": count, "message": f"Synced {count} CVs from data/cvs"}

@app.post("/api/profile/save")
async def save_profile(profile_data: dict):
    """
    Save updated profile data back to the store.
    """
    try:
        from src.data.mock_profiles import MOCK_PROFILES
        from src.schemas.candidate import CandidateProfile
        
        # In a real app, we'd persist this to a DB. For MVP, we update MOCK_PROFILES.
        MOCK_PROFILES["custom"] = CandidateProfile(**profile_data)
        
        return {"status": "success", "message": "Profile updated successfully"}
    except Exception as e:
        logger.error(f"Save failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat")
async def chat(req: ChatRequest):
    logger.info(f"API Chat request: {req.message}")
    try:
        # MVP: Inject Selected Profile
        from src.data.mock_profiles import MOCK_PROFILES
        candidate = MOCK_PROFILES.get("custom")
        if not candidate:
            # Create a valid dummy candidate so validation doesn't fail
            from src.schemas.candidate import CandidateProfile
            candidate = CandidateProfile(
                full_name="Guest", 
                email="guest@example.com", 
                location="Unknown", 
                cv_text="This is a dummy CV for testing purposes only. It has enough length to pass validation rules."
            )
        
        inputs = {
            "messages": [HumanMessage(content=req.message)], 
            "query": req.message,
            "candidate": candidate
        }
        
        # Use simple invoke (graph might contain sync nodes)
        state = graph.invoke(inputs)
        
        messages = state.get("messages", [])
        last_msg = messages[-1].content if messages else "No response."
        
        # Determine agent/status
        agent_name = "RecruitAI"
        offers = state.get("offers_analyzed") or []
        offers_count = len(offers)
        
        if offers_count > 0:
            agent_name = "Job Pipeline"
        elif "documents" in last_msg.lower() or "cv" in last_msg.lower():
            agent_name = "RAG Agent"
        
        return {
            "response": last_msg,
            "agent": agent_name,
            "offers_count": offers_count
        }
    except Exception as e:
        logger.error(f"API Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/jobs")
def get_jobs():
    """
    Return the latest matched jobs from the agent pipeline.
    """
    try:
        from src.config.settings import settings
        from pathlib import Path
        import json
        
        path = Path(settings.DATA_DIR) / "matches.json"
        if not path.exists():
            return []
            
        matches = json.loads(path.read_text(encoding="utf-8"))
        # Map fields for UI
        # UI expects: id, title, company, location... matches has 'score'
        
        results = []
        for i, m in enumerate(matches):
            results.append({
                "id": str(m.get("url") or i),
                "title": m.get("title", "Unknown"),
                "company": m.get("company", "Unknown"),
                "location": m.get("location", "Unknown"),
                "matchScore": int(m.get("score", 0)),
                "description": m.get("summary") or m.get("title"),
                "skills": m.get("skills", []),
                "requirements": m.get("requirements", []),
                "url": m.get("url"),
                "salary": m.get("salary", "N/A"),
                "type": m.get("type", "Full-time"),
                "postedDate": m.get("postedDate", "Recently")
            })
            
        return results
    except Exception as e:
        logger.error(f"Failed to fetch jobs: {e}")
        return [] 

# --- Applications Endpoints ---

@app.get("/api/applications")
def get_applications():
    from src.data.mock_applications import MOCK_APPLICATIONS
    return list(MOCK_APPLICATIONS.values())

@app.post("/api/applications")
def add_application(app_data: dict):
    from src.data.mock_applications import MOCK_APPLICATIONS, Application
    
    app_id = str(uuid.uuid4())
    new_app = Application(
        id=app_id,
        title=app_data.get("title", "Unknown"),
        company=app_data.get("company", "Unknown"),
        location=app_data.get("location", "Unknown"),
        salary=app_data.get("salary", "N/A"),
        matchScore=app_data.get("matchScore", 0),
        stage=app_data.get("stage", "saved"),
        appliedDate=datetime.now().strftime("%b %d, %Y")
    )
    MOCK_APPLICATIONS[app_id] = new_app
    return new_app

@app.patch("/api/applications/{app_id}")
def update_application(app_id: str, updates: dict):
    from src.data.mock_applications import MOCK_APPLICATIONS
    if app_id not in MOCK_APPLICATIONS:
        raise HTTPException(status_code=404, detail="Application not found")
    
    app = MOCK_APPLICATIONS[app_id]
    if "stage" in updates:
        app.stage = updates["stage"]
    
    return app
