import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from typing import List, Optional, get_args
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, File, HTTPException, Query, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from psycopg_pool import PoolTimeout
from pydantic import BaseModel, Field, field_validator

from src.api.auth import check_config, current_user
from src.config.logging import logger
from src.config.settings import settings
from src.schemas.job_offer import SheetContract, SheetRemote, SheetSeniority
from src.storage import db

check_config()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    db.close_pool()


# In production, don't publish the API's map (/docs, /redoc, /openapi.json); locally it stays available
_public_docs = settings.APP_ENV != "production"
app = FastAPI(title="Career Mate API", lifespan=lifespan,
              docs_url="/docs" if _public_docs else None,
              redoc_url="/redoc" if _public_docs else None,
              openapi_url="/openapi.json" if _public_docs else None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Search-Mode"],  # lets the UI tell when search fell back to keywords only
)

User = Depends(current_user)  # every /api route below runs for the signed-in user only


@app.exception_handler(PoolTimeout)
async def database_busy(request, exc):
    """All pooled connections stayed busy: a clear, retryable 503 (with CORS headers) instead of a crash."""
    logger.error(f"[db] no free database connection for {request.method} {request.url.path}")
    return JSONResponse(status_code=503, content={"detail": "The database is busy right now, please retry in a moment."})


@app.get("/health")
def health():
    return {"status": "ok"}


# --- Profile (parsed CV) ---

@app.get("/api/profile/current")
def get_current_profile(uid: str = User):
    from src.ingestion.resume_parser import load_saved_profile
    with db.connection() as conn:
        profile = load_saved_profile(conn, uid)
    if not profile:  # empty state until a CV is uploaded
        return {"key": None, "name": "", "title": "", "email": "", "location": "", "skills": [], "summary": "", "experience": []}
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
        "cv_text": profile.cv_text,
    }


@app.post("/api/upload_resume")
async def upload_resume(file: UploadFile = File(...), uid: str = User):
    """Parse the CV, then store the profile and the file itself for this user."""
    from src.ingestion.resume_parser import parse_cv, read_upload, save_cv
    try:
        name, content = await read_upload(file)
        profile, raw_data = await asyncio.to_thread(parse_cv, name, content)
    except ValueError as e:  # wrong type, too large, unreadable
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail="Could not parse the CV")

    def save():
        with db.connection() as conn:
            save_cv(conn, uid, profile, name, content)
    await asyncio.to_thread(save)
    return {"status": "success", "profile": raw_data, "message": "Resume saved and parsed."}


@app.post("/api/profile/save")
def save_profile(profile_data: dict, uid: str = User):
    from src.schemas.candidate import CandidateProfile
    try:
        profile = CandidateProfile(**profile_data)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    with db.connection() as conn:
        db.save_profile(conn, uid, profile.model_dump())
    return {"status": "success", "message": "Profile updated successfully"}


class PreferencesIn(BaseModel):
    instructions: str = Field(default="", max_length=db.MAX_INSTRUCTIONS_CHARS)


@app.get("/api/preferences")
def get_preferences(uid: str = User):
    with db.connection() as conn:
        return {"instructions": db.get_instructions(conn, uid)}


@app.put("/api/preferences")
def put_preferences(req: PreferencesIn, uid: str = User):
    with db.connection() as conn:
        return {"instructions": db.save_instructions(conn, uid, req.instructions)}


def _writer_offer(o: dict):
    """A saved offer in the shape the writer expects (no extra model call: it is already structured)."""
    from src.schemas.job_offer import OfferAnalyzed
    return OfferAnalyzed(url=o["url"] or "https://internal.app", title=o["title"], company=o["company"],
                         location=o["location"], skills=o["skills"], missions=o["missions"],
                         requirements=o["requirements"], summary=o["summary"])


@app.post("/api/generate")
def generate_content(payload: dict, uid: str = User):
    """Tailored content (cover letter, cold email, interview prep), written from the profile.

    With `offer_id`: written for that saved offer and stored on it as a new version (returned as `document`).
    Otherwise from a pasted `job_description`, analyzed first, and not stored.
    `instructions` overrides the saved personal instructions for this generation only.
    """
    from src.agents.analyzer import analyze_offer_llm, heuristic_analyze_offer
    from src.agents.writer import DOC_TYPES, generate_documents
    from src.ingestion.resume_parser import load_saved_profile
    from src.llm.port import llm, prompt_version
    from src.schemas.job_offer import OfferRaw
    from src.utils.prompts import load_prompt

    doc_type = payload.get("type", "cover-letter")
    raw_jd = payload.get("job_description", "")
    extra = payload.get("extra", "professional")
    offer_id = payload.get("offer_id")
    if doc_type not in DOC_TYPES:
        raise HTTPException(status_code=422, detail=f"type must be one of {', '.join(DOC_TYPES)}")
    if not raw_jd and not offer_id:
        raise HTTPException(status_code=400, detail="Job description required.")

    with db.connection() as conn:
        candidate = load_saved_profile(conn, uid)
        instructions = payload.get("instructions")
        if instructions is None:
            instructions = db.get_instructions(conn, uid)
        offer = db.get_offer(conn, uid, offer_id) if offer_id else None
    instructions = str(instructions)[:db.MAX_INSTRUCTIONS_CHARS]
    if not candidate:
        raise HTTPException(status_code=400, detail="No profile found. Please upload a CV first.")

    if offer_id:
        if not offer:
            raise HTTPException(status_code=404, detail="Offer not found")
        content = generate_documents(candidate, _writer_offer(offer), doc_type=doc_type, extra=extra,
                                     instructions=instructions)
        template = {"cover-letter": "writer_letter", "cold-email": "writer_email", "interview": "writer_interview"}[doc_type]
        with db.connection() as conn:
            document = db.add_document(conn, uid, offer["id"], doc_type, content,
                                       settings={"extra": extra, "instructions": instructions},
                                       model=llm.config("write").model, prompt_version=prompt_version(load_prompt(template)))
        return {"status": "success", "content": content, "document": document}

    # Use the first line as the title if it is short
    initial_title = "Target Position"
    lines = [l.strip() for l in raw_jd.split('\n') if l.strip()]
    if lines and len(lines[0]) < 60:
        initial_title = lines[0]

    temp_offer = OfferRaw(source="custom_input", title=initial_title, company="Target Company",
                          location="Remote", description=raw_jd, url="https://internal.app")
    try:
        analyzed_offer = analyze_offer_llm(temp_offer)
        if analyzed_offer.title == "Target Position" and initial_title != "Target Position":
            analyzed_offer.title = initial_title
    except Exception as e:
        logger.warning(f"Generator flow: LLM analysis failed, falling back to heuristic. Error: {e}")
        analyzed_offer = heuristic_analyze_offer(temp_offer)

    return {"status": "success", "content": generate_documents(candidate, analyzed_offer, doc_type=doc_type, extra=extra,
                                                               instructions=instructions)}


@app.get("/api/offers/{offer_id}/documents")
def get_documents(offer_id: str, type: Optional[str] = None, uid: str = User):
    """Every saved version for the offer, newest first."""
    with db.connection() as conn:
        if not db.get_offer(conn, uid, offer_id):
            raise HTTPException(status_code=404, detail="Offer not found")
        return db.list_documents(conn, uid, offer_id, type)


class RevisionIn(BaseModel):
    """Either `feedback` (the AI rewrites the document) or `content` (your own edit), saved as a new version."""
    feedback: Optional[str] = Field(default=None, max_length=2000)
    content: Optional[str] = Field(default=None, max_length=50000)


@app.post("/api/documents/{document_id}/revise", status_code=201)
def revise(document_id: str, req: RevisionIn, uid: str = User):
    from src.agents.writer import revise_document
    from src.ingestion.resume_parser import load_saved_profile
    from src.llm.port import LLMError, llm, prompt_version
    from src.utils.prompts import load_prompt

    feedback, content = (req.feedback or "").strip(), (req.content or "").strip()
    if bool(feedback) == bool(content):
        raise HTTPException(status_code=422, detail="Send either feedback or content")
    with db.connection() as conn:
        current = db.get_document(conn, uid, document_id)
        if not current:
            raise HTTPException(status_code=404, detail="Document not found")
        offer = db.get_offer(conn, uid, current["offer_id"])
        candidate = load_saved_profile(conn, uid) if feedback else None
        instructions = db.get_instructions(conn, uid)

    settings, model, version = {**current["settings"], "instructions": instructions}, None, None
    if feedback:
        if not candidate:
            raise HTTPException(status_code=400, detail="No profile found. Please upload a CV first.")
        try:  # the model call happens without holding a DB connection
            content = revise_document(candidate, _writer_offer(offer), current["doc_type"], current["content"],
                                      feedback, instructions)
        except (LLMError, ValueError) as e:  # nothing is saved when the model fails
            raise HTTPException(status_code=503, detail=f"Could not revise the document: {str(e)[:200]}")
        model, version = llm.config("write").model, prompt_version(load_prompt("writer_revise"))
    with db.connection() as conn:
        return db.add_document(conn, uid, current["offer_id"], current["doc_type"], content, parent_id=current["id"],
                               feedback=feedback or "Edited by hand", settings=settings, model=model,
                               prompt_version=version, actor="ai" if feedback else "user")


# --- Applications ---
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
def get_applications(uid: str = User):
    with db.connection() as conn:
        return [_to_application(o) for o in db.list_offers(conn, uid)]


@app.patch("/api/applications/{app_id}")
def update_application(app_id: str, updates: dict, uid: str = User):
    with db.connection() as conn:
        offer = db.get_offer_by_application(conn, uid, app_id)
        if not offer:
            raise HTTPException(status_code=404, detail="Application not found")
        try:
            if "stage" in updates:
                offer = db.update_status(conn, uid, app_id, updates["stage"])
            if "folder_id" in updates:  # null = unfiled (drag back to "Unfiled")
                offer = db.set_folder(conn, uid, app_id, updates["folder_id"] or None)
            if "notes" in updates:
                offer = db.set_notes(conn, uid, app_id, str(updates["notes"] or "")[:20000])
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        return _to_application(offer)


# --- Offers (capture) ---

class CaptureRequest(BaseModel):
    url: Optional[str] = None
    text: Optional[str] = None


@app.post("/api/offers/capture")
def capture(req: CaptureRequest, uid: str = User):
    from src.agents.capture import capture_offer, CaptureError

    url = req.url.strip().split("#")[0] if req.url and req.url.strip() else None
    text = req.text.strip() if req.text and req.text.strip() else None

    if url and not text:
        with db.connection() as conn:
            if existing := db.find_offer_by_url(conn, uid, url):
                return {"offer": existing, "duplicate": True}
    try:  # fetch + LLM extraction: no DB connection held meanwhile
        fields = capture_offer(url=url, text=text)
    except CaptureError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"[capture] failed for {url}: {e}")
        raise HTTPException(status_code=502, detail=f"Capture failed: {e}")
    with db.connection() as conn:
        if url and (existing := db.find_offer_by_url(conn, uid, url)):
            # pasted text for a URL already captured: keep the first sheet
            return {"offer": existing, "duplicate": True}
        return {"offer": db.insert_offer(conn, uid, fields, actor="ai"), "duplicate": False}


@app.get("/api/offers")
def get_offers(
    response: Response,
    q: Optional[str] = None,
    status: List[str] = Query(default=[]),
    folder: Optional[str] = None,  # folder id, or "unfiled"
    contract_type: List[str] = Query(default=[]),
    remote_policy: List[str] = Query(default=[]),
    deadline_before: Optional[str] = None,
    sort: Optional[str] = None,  # recent | deadline | title | company | updated | relevance
    mode: str = "hybrid",  # hybrid | keyword | semantic
    uid: str = User,
):
    """Search (keyword full-text + semantic embeddings, fused) + filters + sort. Same filter keys as saved views."""
    from src.storage.offer_search import MODES, search_offers
    if mode not in MODES:
        raise HTTPException(status_code=422, detail=f"mode must be one of {', '.join(MODES)}")
    # search_offers opens short connections itself, and none while the embedding provider is called
    offers, used = search_offers(db.connection, uid, {
        "q": q, "status": status, "folder": folder, "contract_type": contract_type,
        "remote_policy": remote_policy, "deadline_before": deadline_before, "sort": sort,
    }, mode=mode)
    response.headers["X-Search-Mode"] = used  # e.g. "keyword (semantic unavailable)" when embeddings fail
    return offers


class InterpretRequest(BaseModel):
    text: str = Field(min_length=1, max_length=500)


@app.post("/api/offers/interpret")
def interpret_query(req: InterpretRequest, uid: str = User):
    """Natural-language search -> {q, filters, folder_id, deadline_before, sort, applied}. The UI applies it as filters."""
    from src.agents.query_interpreter import interpret
    from src.llm.port import LLMError
    try:  # interpret reads the folders, then calls the model with no DB connection held
        return interpret(db.connection, uid, req.text)
    except LLMError as e:  # quota, missing key, invalid output: the user can still search by keywords
        raise HTTPException(status_code=503, detail=f"Could not interpret the request: {str(e)[:200]}")


@app.get("/api/offer-facets")
def get_offer_facets(uid: str = User):
    with db.connection() as conn:
        return db.offer_facets(conn, uid)


@app.get("/api/offers/{offer_id}")
def get_offer(offer_id: str, uid: str = User):
    with db.connection() as conn:
        offer = db.get_offer(conn, uid, offer_id)
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")
    return offer


# --- Manual offers, folders, contacts ---

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
def create_offer(req: ManualOffer, uid: str = User):
    """Manual offer card: same fields and normalization as a captured offer."""
    with db.connection() as conn:
        if req.url and (existing := db.find_offer_by_url(conn, uid, req.url)):
            raise HTTPException(status_code=409, detail={"message": "This link is already saved", "offer_id": existing["id"]})
        data = req.model_dump(exclude={"status", "folder_id", "notes"})
        try:
            offer = db.insert_offer(conn, uid, {**data, "source": "manual"}, status=req.status, actor="user")
            if req.folder_id:
                offer = db.set_folder(conn, uid, offer["application_id"], req.folder_id)
            if req.notes:
                offer = db.set_notes(conn, uid, offer["application_id"], req.notes)
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
def patch_offer(offer_id: str, req: OfferPatch, uid: str = User):
    changes = req.model_dump(exclude_unset=True)
    with db.connection() as conn:
        if changes.get("url") and (other := db.find_offer_by_url(conn, uid, changes["url"])) and other["id"] != offer_id:
            raise HTTPException(status_code=409, detail={"message": "Another offer already has this link", "offer_id": other["id"]})
        offer = db.update_offer(conn, uid, offer_id, changes)
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")
    return offer


@app.delete("/api/offers/{offer_id}", status_code=204)
def remove_offer(offer_id: str, uid: str = User):
    """Deletes the offer and everything attached to it (contacts, documents, assistant conversation)."""
    with db.connection() as conn:
        if not db.delete_offer(conn, uid, offer_id):
            raise HTTPException(status_code=404, detail="Offer not found")


class ViewIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    filters: dict = {}
    layout: str = "grid"


def _save_view(uid: str, req: ViewIn, view_id: Optional[str] = None):
    allowed = {"q", "status", "folder", "contract_type", "remote_policy", "deadline_before", "sort"}
    filters = {k: v for k, v in req.filters.items() if k in allowed and v not in (None, "", [])}
    with db.connection() as conn:
        try:
            return db.save_view(conn, uid, req.name, filters, req.layout, view_id)
        except db.IntegrityError:
            raise HTTPException(status_code=409, detail="A view with this name already exists")
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        except KeyError:
            raise HTTPException(status_code=404, detail="View not found")


@app.get("/api/views")
def get_views(uid: str = User):
    with db.connection() as conn:
        return db.list_views(conn, uid)


@app.post("/api/views", status_code=201)
def post_view(req: ViewIn, uid: str = User):
    return _save_view(uid, req)


@app.put("/api/views/{view_id}")
def put_view(view_id: str, req: ViewIn, uid: str = User):
    return _save_view(uid, req, view_id)


@app.delete("/api/views/{view_id}", status_code=204)
def remove_view(view_id: str, uid: str = User):
    with db.connection() as conn:
        if not db.delete_view(conn, uid, view_id):
            raise HTTPException(status_code=404, detail="View not found")


class FolderIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)


@app.get("/api/folders")
def get_folders(uid: str = User):
    with db.connection() as conn:
        return db.list_folders(conn, uid)


@app.post("/api/folders", status_code=201)
def post_folder(req: FolderIn, uid: str = User):
    with db.connection() as conn:
        try:
            return db.create_folder(conn, uid, req.name)
        except db.IntegrityError:
            raise HTTPException(status_code=409, detail="A folder with this name already exists")
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))


@app.patch("/api/folders/{folder_id}")
def patch_folder(folder_id: str, req: FolderIn, uid: str = User):
    with db.connection() as conn:
        try:
            if not db.rename_folder(conn, uid, folder_id, req.name):
                raise HTTPException(status_code=404, detail="Folder not found")
        except db.IntegrityError:
            raise HTTPException(status_code=409, detail="A folder with this name already exists")
        return {"id": folder_id, "name": req.name.strip()}


@app.delete("/api/folders/{folder_id}", status_code=204)
def remove_folder(folder_id: str, uid: str = User):
    with db.connection() as conn:
        if not db.delete_folder(conn, uid, folder_id):
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
def get_contacts(app_id: str, uid: str = User):
    with db.connection() as conn:
        return db.list_contacts(conn, uid, app_id)


@app.post("/api/applications/{app_id}/contacts", status_code=201)
def post_contact(app_id: str, req: ContactIn, uid: str = User):
    with db.connection() as conn:
        contact = db.add_contact(conn, uid, app_id, req.model_dump())
    if not contact:
        raise HTTPException(status_code=404, detail="Application not found")
    return contact


@app.patch("/api/contacts/{contact_id}")
def patch_contact(contact_id: str, req: ContactPatch, uid: str = User):
    with db.connection() as conn:
        contact = db.update_contact(conn, uid, contact_id, req.model_dump(exclude_unset=True))
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return contact


@app.delete("/api/contacts/{contact_id}", status_code=204)
def remove_contact(contact_id: str, uid: str = User):
    with db.connection() as conn:
        if not db.delete_contact(conn, uid, contact_id):
            raise HTTPException(status_code=404, detail="Contact not found")


# --- Assistant (pop-up chat about an offer or the profile) ---

class AssistantMessageIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    attachments: List[str] = Field(default=[], max_length=3)  # ids of saved documents


@app.get("/api/assistant/conversation")
def get_assistant_conversation(offer_id: Optional[str] = None, uid: str = User):
    """Open (or create) the conversation for an offer, or the profile one without offer_id, with its history."""
    from src.agents import assistant
    with db.connection() as conn:
        conv = assistant.get_or_create_conversation(conn, uid, offer_id)
        if not conv:
            raise HTTPException(status_code=404, detail="Offer not found")
        return {"conversation": conv, "messages": assistant.list_messages(conn, uid, conv["id"]),
                "actions": assistant.list_actions(conn, uid, conv["id"])}


@app.post("/api/assistant/conversations/{conversation_id}/messages")
def post_assistant_message(conversation_id: str, req: AssistantMessageIn, uid: str = User):
    from src.agents import assistant
    from src.llm.port import LLMError
    try:
        out = assistant.run_turn(uid, conversation_id, req.text, req.attachments)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except LLMError as e:  # quota, provider down: the question is saved, the user can retry
        raise HTTPException(status_code=503, detail=f"The assistant is unavailable right now: {str(e)[:200]}")
    if out is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return out


@app.delete("/api/assistant/conversations/{conversation_id}/messages", status_code=204)
def clear_assistant_conversation(conversation_id: str, uid: str = User):
    from src.agents import assistant
    with db.connection() as conn:
        if not assistant.clear_conversation(conn, uid, conversation_id):
            raise HTTPException(status_code=404, detail="Conversation not found")


class ActionDecisionIn(BaseModel):
    confirm: bool


@app.post("/api/assistant/actions/{action_id}")
def decide_assistant_action(action_id: str, req: ActionDecisionIn, uid: str = User):
    """Apply (confirm) or cancel a change the assistant proposed."""
    from src.agents import assistant
    with db.connection() as conn:
        try:
            action = assistant.decide_action(conn, uid, action_id, req.confirm)
        except ValueError as e:
            raise HTTPException(status_code=409, detail=str(e))
        if not action:
            raise HTTPException(status_code=404, detail="Action not found")
        return {"action": action, "messages": assistant.list_messages(conn, uid, action["conversation_id"])}


# --- Company directory ---

class LinkIn(BaseModel):
    label: str = Field(default="", max_length=80)
    url: str = Field(max_length=2000)


class CompanyIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    website: Optional[str] = Field(default=None, max_length=2000)
    links: List[LinkIn] = []
    notes: str = Field(default="", max_length=20000)


class CompanyPatch(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    website: Optional[str] = Field(default=None, max_length=2000)
    links: Optional[List[LinkIn]] = None


class NoteIn(BaseModel):
    body: str = Field(min_length=1, max_length=5000)
    flag: Optional[str] = None      # important | follow-up | question | risk
    pinned: bool = False


class NotePatch(BaseModel):
    body: Optional[str] = Field(default=None, min_length=1, max_length=5000)
    flag: Optional[str] = None      # send null to remove the flag
    pinned: Optional[bool] = None


class TodoIn(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    due_date: Optional[str] = None


class TodoPatch(BaseModel):
    text: Optional[str] = Field(default=None, min_length=1, max_length=500)
    done: Optional[bool] = None
    due_date: Optional[str] = None


@app.get("/api/companies")
def get_companies(uid: str = User):
    from src.storage import companies
    with db.connection() as conn:
        return companies.list_companies(conn, uid)


@app.get("/api/companies/by-name")
def get_company_by_name(name: str, uid: str = User):
    """The company file for an offer's company name, or 404 if you have none yet."""
    from src.storage import companies
    with db.connection() as conn:
        c = companies.find_company(conn, uid, name)
    if not c:
        raise HTTPException(status_code=404, detail="No company file with this name")
    return c


@app.post("/api/companies", status_code=201)
def post_company(req: CompanyIn, uid: str = User):
    from src.storage import companies
    with db.connection() as conn:
        try:
            return companies.create_company(conn, uid, req.model_dump())
        except db.IntegrityError:
            raise HTTPException(status_code=409, detail="You already have a company with this name")
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))


@app.get("/api/companies/{company_id}")
def get_company(company_id: str, uid: str = User):
    from src.storage import companies
    with db.connection() as conn:
        c = companies.get_company(conn, uid, company_id)
    if not c:
        raise HTTPException(status_code=404, detail="Company not found")
    return c


@app.patch("/api/companies/{company_id}")
def patch_company(company_id: str, req: CompanyPatch, uid: str = User):
    from src.storage import companies
    with db.connection() as conn:
        try:
            c = companies.update_company(conn, uid, company_id, req.model_dump(exclude_unset=True))
        except db.IntegrityError:
            raise HTTPException(status_code=409, detail="You already have a company with this name")
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
    if not c:
        raise HTTPException(status_code=404, detail="Company not found")
    return c


@app.delete("/api/companies/{company_id}", status_code=204)
def remove_company(company_id: str, uid: str = User):
    from src.storage import companies
    with db.connection() as conn:
        if not companies.delete_company(conn, uid, company_id):
            raise HTTPException(status_code=404, detail="Company not found")


@app.post("/api/companies/{company_id}/todos", status_code=201)
def post_todo(company_id: str, req: TodoIn, uid: str = User):
    from src.storage import companies
    with db.connection() as conn:
        try:
            todo = companies.add_todo(conn, uid, company_id, req.model_dump(exclude_unset=True))
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
    if not todo:
        raise HTTPException(status_code=404, detail="Company not found")
    return todo


@app.patch("/api/todos/{todo_id}")
def patch_todo(todo_id: str, req: TodoPatch, uid: str = User):
    from src.storage import companies
    with db.connection() as conn:
        try:
            todo = companies.update_todo(conn, uid, todo_id, req.model_dump(exclude_unset=True))
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
    if not todo:
        raise HTTPException(status_code=404, detail="To-do not found")
    return todo


@app.delete("/api/todos/{todo_id}", status_code=204)
def remove_todo(todo_id: str, uid: str = User):
    from src.storage import companies
    with db.connection() as conn:
        if not companies.delete_todo(conn, uid, todo_id):
            raise HTTPException(status_code=404, detail="To-do not found")


@app.post("/api/companies/{company_id}/notes", status_code=201)
def post_company_note(company_id: str, req: NoteIn, uid: str = User):
    from src.storage import companies
    with db.connection() as conn:
        try:
            note = companies.add_note(conn, uid, company_id, req.model_dump())
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
    if not note:
        raise HTTPException(status_code=404, detail="Company not found")
    return note


@app.patch("/api/company-notes/{note_id}")
def patch_company_note(note_id: str, req: NotePatch, uid: str = User):
    from src.storage import companies
    with db.connection() as conn:
        try:
            note = companies.update_note(conn, uid, note_id, req.model_dump(exclude_unset=True))
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return note


@app.delete("/api/company-notes/{note_id}", status_code=204)
def remove_company_note(note_id: str, uid: str = User):
    from src.storage import companies
    with db.connection() as conn:
        if not companies.delete_note(conn, uid, note_id):
            raise HTTPException(status_code=404, detail="Note not found")


# --- Outreach messages: categories, reference library, drafts ---

class CategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class TemplateIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    body: str = Field(min_length=1, max_length=20000)
    channel: str = "linkedin-message"
    category_id: Optional[str] = None
    pinned: bool = False
    # Pinning a draft written for an offer/contact: turn their names back into placeholders
    generalize_offer_id: Optional[str] = None
    generalize_contact_id: Optional[str] = None


class TemplatePatch(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=120)
    body: Optional[str] = Field(default=None, min_length=1, max_length=20000)
    channel: Optional[str] = None
    category_id: Optional[str] = None
    pinned: Optional[bool] = None


class RenderIn(BaseModel):
    body: str = Field(max_length=20000)
    offer_id: Optional[str] = None
    contact_id: Optional[str] = None


class OutreachIn(BaseModel):
    body: str = Field(min_length=1, max_length=20000)
    channel: str = "linkedin-message"
    category_id: Optional[str] = None
    template_id: Optional[str] = None
    offer_id: Optional[str] = None
    contact_id: Optional[str] = None


class OutreachPatch(BaseModel):
    body: Optional[str] = Field(default=None, min_length=1, max_length=20000)
    channel: Optional[str] = None
    category_id: Optional[str] = None
    offer_id: Optional[str] = None
    contact_id: Optional[str] = None
    status: Optional[str] = None   # draft | sent


def _outreach_call(fn, *args, not_found: str = "Not found"):
    """Run an outreach storage call: 422 on invalid input, 409 on a duplicate name, 404 when it isn't yours."""
    with db.connection() as conn:
        try:
            result = fn(conn, *args)
        except db.IntegrityError:
            raise HTTPException(status_code=409, detail="A category with this name already exists")
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
    if result is None or result is False:
        raise HTTPException(status_code=404, detail=not_found)
    return result


@app.get("/api/outreach/categories")
def get_message_categories(uid: str = User):
    from src.storage import outreach
    return _outreach_call(outreach.list_categories, uid)


@app.post("/api/outreach/categories", status_code=201)
def post_message_category(req: CategoryIn, uid: str = User):
    from src.storage import outreach
    return _outreach_call(outreach.create_category, uid, req.name)


@app.patch("/api/outreach/categories/{category_id}")
def patch_message_category(category_id: str, req: CategoryIn, uid: str = User):
    from src.storage import outreach
    return _outreach_call(outreach.rename_category, uid, category_id, req.name, not_found="Category not found")


@app.delete("/api/outreach/categories/{category_id}", status_code=204)
def remove_message_category(category_id: str, uid: str = User):
    from src.storage import outreach
    _outreach_call(outreach.delete_category, uid, category_id, not_found="Category not found")


@app.get("/api/outreach/templates")
def get_message_templates(category_id: Optional[str] = None, uid: str = User):
    from src.storage import outreach
    return _outreach_call(outreach.list_templates, uid, category_id)


@app.post("/api/outreach/templates", status_code=201)
def post_message_template(req: TemplateIn, uid: str = User):
    from src.storage import outreach
    data = req.model_dump(exclude={"generalize_offer_id", "generalize_contact_id"})
    if req.generalize_offer_id or req.generalize_contact_id:
        with db.connection() as conn:
            values = outreach.placeholder_values(conn, uid, req.generalize_offer_id, req.generalize_contact_id)
        data["body"] = outreach.generalize(data["body"], values)
    return _outreach_call(outreach.create_template, uid, data)


@app.patch("/api/outreach/templates/{template_id}")
def patch_message_template(template_id: str, req: TemplatePatch, uid: str = User):
    from src.storage import outreach
    return _outreach_call(outreach.update_template, uid, template_id, req.model_dump(exclude_unset=True),
                          not_found="Reference message not found")


@app.delete("/api/outreach/templates/{template_id}", status_code=204)
def remove_message_template(template_id: str, uid: str = User):
    from src.storage import outreach
    _outreach_call(outreach.delete_template, uid, template_id, not_found="Reference message not found")


@app.post("/api/outreach/render")
def render_message(req: RenderIn, uid: str = User):
    """Fill the placeholders of a text for an offer and contact: {body, missing, values}."""
    from src.storage import outreach
    with db.connection() as conn:
        values = outreach.placeholder_values(conn, uid, req.offer_id, req.contact_id)
    return {**outreach.fill(req.body, values), "values": values}


@app.get("/api/outreach/messages")
def get_outreach_messages(status: Optional[str] = None, uid: str = User):
    from src.storage import outreach
    return _outreach_call(outreach.list_messages, uid, status)


@app.post("/api/outreach/messages", status_code=201)
def post_outreach_message(req: OutreachIn, uid: str = User):
    from src.storage import outreach
    return _outreach_call(outreach.create_message, uid, req.model_dump())


@app.patch("/api/outreach/messages/{message_id}")
def patch_outreach_message(message_id: str, req: OutreachPatch, uid: str = User):
    from src.storage import outreach
    return _outreach_call(outreach.update_message, uid, message_id, req.model_dump(exclude_unset=True),
                          not_found="Message not found")


@app.delete("/api/outreach/messages/{message_id}", status_code=204)
def remove_outreach_message(message_id: str, uid: str = User):
    from src.storage import outreach
    _outreach_call(outreach.delete_message, uid, message_id, not_found="Message not found")


class AdaptIn(BaseModel):
    body: str = Field(min_length=1, max_length=20000)
    channel: str = "linkedin-message"
    offer_id: Optional[str] = None
    contact_id: Optional[str] = None
    extra: str = Field(default="", max_length=500)   # e.g. "mention their dbt talk", "more formal"


@app.post("/api/outreach/adapt")
def adapt_message(req: AdaptIn, uid: str = User):
    """Personalize a message with AI for an offer and contact. Not saved: the user reviews it first."""
    from src.agents.outreach_writer import adapt
    from src.llm.port import LLMError
    try:
        return adapt(uid, req.body, req.channel, req.offer_id, req.contact_id, req.extra)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except LLMError as e:
        raise HTTPException(status_code=503, detail=f"The AI is unavailable right now: {str(e)[:200]}")
