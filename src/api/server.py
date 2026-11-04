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
        try:
            if "stage" in updates:
                offer = db.update_status(conn, app_id, updates["stage"])
            if "folder_id" in updates:  # null = unfiled (drag back to "Unfiled")
                offer = db.set_folder(conn, app_id, updates["folder_id"] or None)
            if "notes" in updates:
                offer = db.set_notes(conn, app_id, str(updates["notes"] or "")[:20000])
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

from fastapi import Query


@app.get("/api/offers")
def get_offers(
    q: Optional[str] = None,
    status: List[str] = Query(default=[]),
    folder: Optional[str] = None,  # folder id, or "unfiled"
    contract_type: List[str] = Query(default=[]),
    remote_policy: List[str] = Query(default=[]),
    deadline_before: Optional[str] = None,
    sort: Optional[str] = None,  # recent | deadline | title | company | updated | relevance
):
    """Search (full text, BM25) + filters + sort. Same filter keys as saved views."""
    with closing(db.connect()) as conn:
        return db.query_offers(conn, {
            "q": q, "status": status, "folder": folder, "contract_type": contract_type,
            "remote_policy": remote_policy,
            "deadline_before": deadline_before, "sort": sort,
        })


@app.get("/api/offer-facets")
def get_offer_facets():
    with closing(db.connect()) as conn:
        return db.offer_facets(conn)

@app.get("/api/offers/{offer_id}")
def get_offer(offer_id: str):
    with closing(db.connect()) as conn:
        offer = db.get_offer(conn, offer_id)
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")
    return offer

# --- Manual offers, folders, contacts ---

from typing import get_args
from urllib.parse import urlparse
from pydantic import Field, field_validator
from src.schemas.job_offer import SheetContract, SheetRemote, SheetSeniority


def _http_url(v: Optional[str]) -> Optional[str]:
    """Links are rendered as <a href>: only http(s) (a javascript: URL would run code on click)."""
    v = (v or "").strip()
    if not v:
        return None
    p = urlparse(v)
    if p.scheme not in ("http", "https") or not p.netloc:
        raise ValueError("must be an http(s):// link")
    return v


def _clean_list(items: List[str]) -> List[str]:
    """Trim, drop empties and case-insensitive duplicates, keep order."""
    seen, out = set(), []
    for x in (i.strip() for i in items):
        if x and x.casefold() not in seen:
            seen.add(x.casefold())
            out.append(x)
    return out


def _check_enum(v: Optional[str], field: str) -> str:
    allowed = get_args({"remote_policy": SheetRemote, "contract_type": SheetContract, "seniority": SheetSeniority}[field])
    if (v or "unknown") not in allowed:
        raise ValueError(f"must be one of {', '.join(allowed)}")
    return v or "unknown"


def _check_date(v: Optional[str]) -> Optional[str]:
    if not v:
        return None
    datetime.strptime(v, "%Y-%m-%d")  # ValueError -> 422
    return v


@app.get("/api/offer-options")
def get_offer_options():
    """Allowed values for the offer form, from the same lists the capture uses."""
    return {"statuses": list(db.STATUSES), "contract_types": list(get_args(SheetContract)),
            "remote_policies": list(get_args(SheetRemote)), "seniorities": list(get_args(SheetSeniority))}


class ManualOffer(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    company: Optional[str] = None
    location: Optional[str] = None
    url: Optional[str] = None
    remote_policy: str = "unknown"
    contract_type: str = "unknown"
    seniority: str = "unknown"
    salary: Optional[str] = None
    deadline: Optional[str] = None
    summary: Optional[str] = None
    raw_text: Optional[str] = Field(default=None, max_length=100000)
    skills: List[str] = []
    nice_to_have: List[str] = []
    missions: List[str] = []
    requirements: List[str] = []
    status: str = "saved"
    folder_id: Optional[str] = None
    notes: Optional[str] = None

    _url = field_validator("url")(lambda cls, v: _http_url(v))
    _lists = field_validator("skills", "nice_to_have", "missions", "requirements")(lambda cls, v: _clean_list(v))

    _enum = field_validator("remote_policy", "contract_type", "seniority")(lambda cls, v, info: _check_enum(v, info.field_name))
    _date = field_validator("deadline")(lambda cls, v: _check_date(v))


@app.post("/api/offers", status_code=201)
def create_offer(req: ManualOffer):
    """Manual offer card: same fields and normalization as a captured offer."""
    with closing(db.connect()) as conn:
        if req.url and (existing := db.find_offer_by_url(conn, req.url)):
            raise HTTPException(status_code=409, detail={"message": "This link is already saved", "offer_id": existing["id"]})
        data = req.model_dump(exclude={"status", "folder_id", "notes"})
        try:
            offer = db.insert_offer(conn, {**data, "source": "manual"}, status=req.status, actor="user")
            if req.folder_id:
                offer = db.set_folder(conn, offer["application_id"], req.folder_id)
            if req.notes:
                offer = db.set_notes(conn, offer["application_id"], req.notes)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        return offer


class OfferPatch(BaseModel):
    """Edit an offer card: send only the fields you change."""
    title: Optional[str] = Field(default=None, min_length=1, max_length=300)
    company: Optional[str] = None
    location: Optional[str] = None
    url: Optional[str] = None
    remote_policy: Optional[str] = None
    contract_type: Optional[str] = None
    seniority: Optional[str] = None
    salary: Optional[str] = None
    deadline: Optional[str] = None
    summary: Optional[str] = None
    raw_text: Optional[str] = Field(default=None, max_length=100000)
    skills: Optional[List[str]] = None
    nice_to_have: Optional[List[str]] = None
    missions: Optional[List[str]] = None
    requirements: Optional[List[str]] = None

    _url = field_validator("url")(lambda cls, v: _http_url(v))
    _lists = field_validator("skills", "nice_to_have", "missions", "requirements")(lambda cls, v: _clean_list(v) if v is not None else v)
    _enum = field_validator("remote_policy", "contract_type", "seniority")(
        lambda cls, v, info: _check_enum(v, info.field_name) if v is not None else v)
    _date = field_validator("deadline")(lambda cls, v: _check_date(v))


@app.patch("/api/offers/{offer_id}")
def patch_offer(offer_id: str, req: OfferPatch):
    changes = req.model_dump(exclude_unset=True)
    with closing(db.connect()) as conn:
        if changes.get("url") and (other := db.find_offer_by_url(conn, changes["url"])) and other["id"] != offer_id:
            raise HTTPException(status_code=409, detail={"message": "Another offer already has this link", "offer_id": other["id"]})
        offer = db.update_offer(conn, offer_id, changes)
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")
    return offer


class ViewIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    filters: dict = {}
    layout: str = "grid"


def _save_view(req: ViewIn, view_id: Optional[str] = None):
    import sqlite3
    allowed = {"q", "status", "folder", "contract_type", "remote_policy", "deadline_before", "sort"}
    filters = {k: v for k, v in req.filters.items() if k in allowed and v not in (None, "", [])}
    with closing(db.connect()) as conn:
        try:
            return db.save_view(conn, req.name, filters, req.layout, view_id)
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail="A view with this name already exists")
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        except KeyError:
            raise HTTPException(status_code=404, detail="View not found")


@app.get("/api/views")
def get_views():
    with closing(db.connect()) as conn:
        return db.list_views(conn)


@app.post("/api/views", status_code=201)
def post_view(req: ViewIn):
    return _save_view(req)


@app.put("/api/views/{view_id}")
def put_view(view_id: str, req: ViewIn):
    return _save_view(req, view_id)


@app.delete("/api/views/{view_id}", status_code=204)
def remove_view(view_id: str):
    with closing(db.connect()) as conn:
        if not db.delete_view(conn, view_id):
            raise HTTPException(status_code=404, detail="View not found")


class FolderIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)


@app.get("/api/folders")
def get_folders():
    with closing(db.connect()) as conn:
        return db.list_folders(conn)


@app.post("/api/folders", status_code=201)
def post_folder(req: FolderIn):
    import sqlite3
    with closing(db.connect()) as conn:
        try:
            return db.create_folder(conn, req.name)
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail="A folder with this name already exists")
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))


@app.patch("/api/folders/{folder_id}")
def patch_folder(folder_id: str, req: FolderIn):
    import sqlite3
    with closing(db.connect()) as conn:
        try:
            if not db.rename_folder(conn, folder_id, req.name):
                raise HTTPException(status_code=404, detail="Folder not found")
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail="A folder with this name already exists")
        return {"id": folder_id, "name": req.name.strip()}


@app.delete("/api/folders/{folder_id}", status_code=204)
def remove_folder(folder_id: str):
    with closing(db.connect()) as conn:
        if not db.delete_folder(conn, folder_id):
            raise HTTPException(status_code=404, detail="Folder not found")


class ContactIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    role: Optional[str] = None
    linkedin_url: Optional[str] = None
    notes: Optional[str] = None
    reached_out: bool = False

    _url = field_validator("linkedin_url")(lambda cls, v: _http_url(v))


class ContactPatch(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    role: Optional[str] = None
    linkedin_url: Optional[str] = None
    notes: Optional[str] = None
    reached_out: Optional[bool] = None

    _url = field_validator("linkedin_url")(lambda cls, v: _http_url(v))


@app.get("/api/applications/{app_id}/contacts")
def get_contacts(app_id: str):
    with closing(db.connect()) as conn:
        return db.list_contacts(conn, app_id)


@app.post("/api/applications/{app_id}/contacts", status_code=201)
def post_contact(app_id: str, req: ContactIn):
    with closing(db.connect()) as conn:
        contact = db.add_contact(conn, app_id, req.model_dump())
    if not contact:
        raise HTTPException(status_code=404, detail="Application not found")
    return contact


@app.patch("/api/contacts/{contact_id}")
def patch_contact(contact_id: str, req: ContactPatch):
    with closing(db.connect()) as conn:
        contact = db.update_contact(conn, contact_id, req.model_dump(exclude_unset=True))
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return contact


@app.delete("/api/contacts/{contact_id}", status_code=204)
def remove_contact(contact_id: str):
    with closing(db.connect()) as conn:
        if not db.delete_contact(conn, contact_id):
            raise HTTPException(status_code=404, detail="Contact not found")
