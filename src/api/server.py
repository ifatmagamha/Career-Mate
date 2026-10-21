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
        "title": profile.summary[:50] + "..." if profile.summary else "My Profile", 
        "email": profile.email,
        "location": profile.location,
        "skills": profile.skills or [],
        "summary": profile.summary or "",
        "experience": profile.experience or [],
        "education": profile.education or [],
        "projects": profile.projects or [],
        "cv_text": profile.cv_text
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

@app.post("/api/generate")
async def generate_content(payload: dict):
    """
    Generates tailored career content (Cover Letter, Email, Interview).
    Flow: Analyze JD -> Fetch Profile -> Generate
    """
    from src.agents.analyzer import analyze_offer_llm
    from src.agents.writer import generate_documents
    from src.schemas.job_offer import OfferRaw
    from src.data.mock_profiles import MOCK_PROFILES
    
    doc_type = payload.get("type", "cover-letter")
    raw_jd = payload.get("job_description", "")
    extra = payload.get("extra", "professional")
    
    if not raw_jd:
        raise HTTPException(status_code=400, detail="Job description required.")
    
    # 1. Fetch Candidate
    candidate = MOCK_PROFILES.get("custom")
    if not candidate:
        raise HTTPException(status_code=400, detail="No profile found. Please upload a CV first.")
        
    # 2. Analyze Job (Agentic step)
    from src.agents.analyzer import heuristic_analyze_offer
    
    # Try to extract a title from the first line if it's short
    initial_title = "Target Position"
    lines = [l.strip() for l in raw_jd.split('\n') if l.strip()]
    if lines and len(lines[0]) < 60:
        initial_title = lines[0]

    temp_offer = OfferRaw(
        source="custom_input",
        title=initial_title,
        company="Target Company",
        location="Remote",
        description=raw_jd,
        url="https://internal.app"
    )
    try:
        analyzed_offer = analyze_offer_llm(temp_offer)
        # If LLM didn't change the placeholder title, try our heuristic again
        if analyzed_offer.title == "Target Position" and initial_title != "Target Position":
            analyzed_offer.title = initial_title
    except Exception as e:
        logger.warning(f"Generator flow: LLM analysis failed, falling back to heuristic. Error: {e}")
        analyzed_offer = heuristic_analyze_offer(temp_offer)
    
    # 3. Generate content
    content = generate_documents(candidate, analyzed_offer, doc_type=doc_type, extra=extra)
    
    return {
        "status": "success",
        "content": content
    }

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

from fastapi.responses import StreamingResponse
import json
import asyncio

@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest):
    async def event_generator():
        # MVP: Inject Selected Profile
        from src.data.mock_profiles import MOCK_PROFILES
        candidate = MOCK_PROFILES.get("custom")
        if not candidate:
            from src.schemas.candidate import CandidateProfile
            candidate = CandidateProfile(
                full_name="Guest", 
                email="guest@example.com", 
                location="Unknown", 
                cv_text="Dummy CV text for testing."
            )
        
        inputs = {
            "messages": [HumanMessage(content=req.message)], 
            "query": req.message,
            "candidate": candidate
        }

        # Step 1: Notify the UI that we are routing/thinking
        yield json.dumps({"type": "status", "data": "RecruitAI is thinking..."}) + "\n"
        
        # Run graph in a separate thread to avoid blocking if nodes are sync
        loop = asyncio.get_event_loop()
        state = await loop.run_in_executor(None, lambda: graph.invoke(inputs))
        
        messages = state.get("messages", [])
        last_msg = messages[-1].text if messages else "No response."
        
        # Simulate word-by-word streaming for the UI "feel"
        words = last_msg.split(" ")
        for i in range(len(words)):
            chunk = words[i] + (" " if i < len(words) - 1 else "")
            yield json.dumps({"type": "chunk", "data": chunk}) + "\n"
            await asyncio.sleep(0.01) # Small delay for cinematic feel
            
        # Final metadata
        node = state.get("active_node")
        agent_name = "RecruitAI"
        if node == "stats": agent_name = "Stats Agent"
        elif node == "rag": agent_name = "RAG Agent"
        elif node == "job_pipeline": agent_name = "Job Pipeline"
        elif node == "chat": agent_name = "RecruitAI"
        
        offers = state.get("offers_analyzed") or []
        yield json.dumps({"type": "done", "agent": agent_name, "offers_count": len(offers)}) + "\n"

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")

@app.post("/api/chat")
async def chat(req: ChatRequest):
    # Keep the original sync chat as fallback
    logger.info(f"API Chat request: {req.message}")
    try:
        from src.data.mock_profiles import MOCK_PROFILES
        candidate = MOCK_PROFILES.get("custom")
        if not candidate:
            from src.schemas.candidate import CandidateProfile
            candidate = CandidateProfile(full_name="Guest", email="guest@example.com", location="Unknown", cv_text="Dummy CV")
        
        inputs = {"messages": [HumanMessage(content=req.message)], "query": req.message, "candidate": candidate}
        state = graph.invoke(inputs)
        last_msg = state.get("messages", [])[-1].text if state.get("messages") else "No response."
        return {"response": last_msg, "agent": "RecruitAI", "offers_count": len(state.get("offers_analyzed") or [])}
    except Exception as e:
        logger.error(f"API Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/system/stats")
def get_system_stats():
    """Returns metadata about the collector and storage."""
    from src.config.settings import settings
    import os
    import json
    
    raw_path = os.path.join(settings.DATA_DIR, "job_offers_raw.json")
    analyzed_path = os.path.join(settings.DATA_DIR, "job_offers_analyzed.json")
    matches_path = os.path.join(settings.DATA_DIR, "matches.json")
    
    stats = {
        "raw_count": 0,
        "analyzed_count": 0,
        "matches_count": 0,
        "last_updated": "Never",
        "storage_dir": settings.DATA_DIR
    }
    
    try:
        if os.path.exists(raw_path):
            with open(raw_path, "r", encoding="utf-8") as f:
                stats["raw_count"] = len(json.load(f))
        
        if os.path.exists(analyzed_path):
            with open(analyzed_path, "r", encoding="utf-8") as f:
                stats["analyzed_count"] = len(json.load(f))
                
        if os.path.exists(matches_path):
            with open(matches_path, "r", encoding="utf-8") as f:
                stats["matches_count"] = len(json.load(f))
                stats["last_updated"] = datetime.fromtimestamp(os.path.getmtime(matches_path)).strftime("%Y-%m-%d %H:%M:%S")
    except:
        pass
        
    return stats

@app.get("/api/jobs")
def get_jobs():
    """
    Return the latest matched jobs from the agent pipeline.
    """
    try:
        from src.config.settings import settings
        from pathlib import Path
        import json
        
        matches_path = Path(settings.DATA_DIR) / "matches.json"
        analyzed_path = Path(settings.DATA_DIR) / "job_offers_analyzed.json"
        
        # Prefer matches.json (scored) over job_offers_analyzed.json (unscored)
        path = matches_path if matches_path.exists() else analyzed_path
        
        if not path.exists():
            return []
            
        data = json.loads(path.read_text(encoding="utf-8"))
        results = []
        for i, m in enumerate(data):
            # Check if it's a MatchResult or OfferAnalyzed (MatchResult has 'score')
            score = m.get("score", 70) # Default if not matched yet
            results.append({
                "id": str(m.get("url") or i),
                "title": m.get("title", "Unknown"),
                "company": m.get("company", "Unknown"),
                "location": m.get("location", "Unknown"),
                "matchScore": int(score),
                "description": m.get("summary") or m.get("title"),
                "skills": m.get("skills", []),
                "requirements": m.get("requirements", []),
                "url": str(m.get("url", "")),
                "salary": m.get("salary", "Competitive"),
                "type": m.get("contract_type", "Full-time"),
                "postedDate": m.get("postedDate", "Today")
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
