import os
import shutil
from pathlib import Path
from typing import Dict, Any, Tuple
from fastapi import UploadFile

from src.config.logging import logger
from src.schemas.candidate import CandidateProfile
from src.agents.parser import parse_resume_text, map_parsed_to_profile
from src.storage.vector_store import create_vector_store

UPLOAD_DIR = Path("data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

async def handle_resume_upload(file: UploadFile, session_id: str = "default_user") -> Tuple[CandidateProfile, Dict[str, Any]]:
    """
    1. Save file.
    2. Extract text (PDF/TXT).
    3. LLM Parse to JSON via specialized Parser Agent.
    4. Index for RAG.
    """
    # 1. Save File
    file_path = UPLOAD_DIR / f"{session_id}_{file.filename}"
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    logger.info(f"[parser] Saved resume to {file_path}")

    # 2. Extract Text
    text_content = ""
    if file.filename.lower().endswith(".pdf"):
        text_content = extract_text_from_pdf(file_path)
    else:
        try:
            text_content = file_path.read_text(encoding="utf-8", errors="ignore")
        except:
            text_content = str(file_path.read_bytes()[:10000]) 

    if len(text_content) < 50:
        raise ValueError("Resume text is too short or unreadable.")

    # 3. LLM Parsing via Parser Agent
    logger.info("[parser] Segmenting and classifying resume text...")
    parsed_data = parse_resume_text(text_content)
    
    if not parsed_data:
        raise ValueError("AI failed to extract structured data from resume.")
    
    # Map to schema
    profile = map_parsed_to_profile(parsed_data, text_content)

    # 4. Index for RAG
    index_profile_for_rag(profile)
    
    return profile, parsed_data

def index_profile_for_rag(profile: CandidateProfile):
    """Creates searchable chunks from the profile."""
    logger.info(f"[parser] Indexing profile for {profile.full_name} in Vector Store...")
    
    # Meaningful chunks for RAG retrieval
    rag_texts = [
        f"Candidate: {profile.full_name}\nContact: {profile.email}\nLocation: {profile.location}",
        f"Professional Summary: {profile.summary}",
        f"Hard Skills: {', '.join(profile.skills)}",
        f"Soft Skills & Languages: {', '.join(profile.soft_skills)}",
        f"Work Experience: {str(profile.experience)}",
        f"Education: {str(profile.education)}",
        f"Projects: {str(profile.projects)}",
        f"Certifications: {str(profile.certifications)}"
    ]
    
    # Filter out empty sections
    rag_texts = [t for t in rag_texts if ":" in t and len(t.split(":")[1].strip()) > 3]
    
    create_vector_store(rag_texts)

async def sync_cvs_folder() -> int:
    """Synced at startup."""
    CV_DIR = Path("data/cvs")
    CV_DIR.mkdir(parents=True, exist_ok=True)
    
    from src.data.mock_profiles import MOCK_PROFILES
    
    files = list(CV_DIR.glob("*.pdf")) + list(CV_DIR.glob("*.txt"))
    if not files: return 0
    
    # Sort to get the latest
    files.sort(key=lambda x: x.stat().st_mtime)
    
    count = 0
    for file_path in files:
        try:
            # Simple mock of what handle_resume_upload does but for local files
            if file_path.suffix.lower() == ".pdf":
                text = extract_text_from_pdf(file_path)
            else:
                text = file_path.read_text(encoding="utf-8", errors="ignore")
            
            if len(text) < 50: continue
            
            parsed = parse_resume_text(text)
            if parsed:
                profile = map_parsed_to_profile(parsed, text)
                MOCK_PROFILES["custom"] = profile
                index_profile_for_rag(profile)
                count += 1
                logger.info(f"[sync] Processed {file_path.name}")
        except Exception as e:
            logger.error(f"[sync] Failed {file_path.name}: {e}")
            
    return count

def extract_text_from_pdf(path: Path) -> str:
    try:
        import pypdf
        reader = pypdf.PdfReader(path)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text.strip()
    except Exception as e:
        logger.error(f"PDF Extraction Error: {e}")
        return ""
