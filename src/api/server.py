from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Any
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import HumanMessage
from contextlib import closing
from datetime import datetime

from src.graph.build_graph import build_recruit_graph
from src.storage import db
from src.config.logging import logger

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
    """Reload the saved profile (data/profile.json); parse the latest CV in data/cvs only if none is saved."""
    from src.ingestion.resume_parser import restore_profile
    from src.data.mock_profiles import MOCK_PROFILES
    try:
        profile = await asyncio.to_thread(restore_profile)
        if profile:
            MOCK_PROFILES["custom"] = profile
        logger.info(f"Startup: profile {'loaded for ' + str(profile.full_name) if profile else 'not found (upload a CV)'}")
    except Exception as e:
        logger.error(f"Startup profile restore failed: {e}")

@app.post("/api/upload_resume")
async def upload_resume(file: UploadFile = File(...)):
    """
    Save the CV in data/cvs, parse it, save the profile and set it as active.
    """
    global ACTIVE_PROFILE_KEY
    try:
        profile, raw_data = await handle_resume_upload(file)
    except ValueError as e:  # wrong type, too large, unreadable
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    from src.data.mock_profiles import MOCK_PROFILES
    MOCK_PROFILES["custom"] = profile
    ACTIVE_PROFILE_KEY = "custom"
    return {
        "status": "success",
        "profile": raw_data,
        "message": "Resume saved, parsed and set as active."
    }

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
        from src.ingestion.resume_parser import save_profile as persist_profile, index_profile_for_rag

        profile = CandidateProfile(**profile_data)
        MOCK_PROFILES["custom"] = profile
        persist_profile(profile)              # survives restarts (data/profile.json)
        await asyncio.to_thread(index_profile_for_rag, profile)  # RAG answers from the edited profile

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
        if node == "rag": agent_name = "RAG Agent"
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

# An application is what I do with an offer (1:1); stage == applications.status

def _to_application(o: dict) -> dict:
    return {
        "id": o["application_id"],
        "offerId": o["id"],
        "title": o["title"],
        "company": o["company"] or "Unknown",
        "location": o["location"] or "Unknown",
        "salary": o["salary"] or "N/A",
        "matchScore": o["match_score"] or 0,
        "stage": o["status"],
        "appliedDate": datetime.fromisoformat(o["applied_at"] or o["created_at"]).strftime("%b %d, %Y"),
    }

@app.get("/api/statuses")
def get_statuses():
    return list(db.STATUSES)

@app.get("/api/applications")
def get_applications():
    with closing(db.connect()) as conn:
        return [_to_application(o) for o in db.list_offers(conn)]

@app.post("/api/applications")
def add_application(app_data: dict):
    with closing(db.connect()) as conn:
        try:
            offer = db.insert_offer(conn, {
                "title": app_data.get("title", "Unknown"),
                "company": app_data.get("company"),
                "location": app_data.get("location"),
                "salary": app_data.get("salary"),
                "match_score": app_data.get("matchScore"),
                "source": "manual",
            }, status=app_data.get("stage", "saved"))
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        return _to_application(offer)

@app.patch("/api/applications/{app_id}")
def update_application(app_id: str, updates: dict):
    with closing(db.connect()) as conn:
        offer = db.get_offer_by_application(conn, app_id)
        if not offer:
            raise HTTPException(status_code=404, detail="Application not found")
        if "stage" in updates:
            try:
                offer = db.update_status(conn, app_id, updates["stage"])
            except ValueError as e:
                raise HTTPException(status_code=422, detail=str(e))
        return _to_application(offer)

# --- Offers (capture) ---

class CaptureRequest(BaseModel):
    url: Optional[str] = None
    text: Optional[str] = None

@app.post("/api/offers/capture")
def capture(req: CaptureRequest):
    from src.agents.capture import capture_offer, CaptureError

    url = req.url.strip().split("#")[0] if req.url and req.url.strip() else None
    text = req.text.strip() if req.text and req.text.strip() else None

    with closing(db.connect()) as conn:
        if url and not text:
            existing = db.find_offer_by_url(conn, url)
            if existing:
                return {"offer": existing, "duplicate": True}
        try:
            fields = capture_offer(url=url, text=text)
        except CaptureError as e:
            raise HTTPException(status_code=422, detail=str(e))
        except Exception as e:
            logger.error(f"[capture] failed for {url}: {e}")
            raise HTTPException(status_code=502, detail=f"Capture failed: {e}")
        if url and db.find_offer_by_url(conn, url):
            # pasted text for a URL already captured: keep the first sheet
            return {"offer": db.find_offer_by_url(conn, url), "duplicate": True}
        return {"offer": db.insert_offer(conn, fields, actor="ai"), "duplicate": False}

@app.get("/api/offers")
def get_offers():
    with closing(db.connect()) as conn:
        return db.list_offers(conn)

@app.get("/api/offers/{offer_id}")
def get_offer(offer_id: str):
    with closing(db.connect()) as conn:
        offer = db.get_offer(conn, offer_id)
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")
    return offer
