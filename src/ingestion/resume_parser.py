import os
import shutil
import json
from pathlib import Path
from typing import Dict, Any
from fastapi import UploadFile
from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import ValidationError

from src.config.settings import settings
from src.config.logging import logger
from src.schemas.candidate import CandidateProfile
from src.utils.prompts import load_prompt

# Initialize LLM
llm = ChatGoogleGenerativeAI(
    model=settings.GEMINI_MODEL,
    google_api_key=settings.GEMINI_API_KEY,
    temperature=0
)

UPLOAD_DIR = Path("data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

async def handle_resume_upload(file: UploadFile, session_id: str = "default_user") -> CandidateProfile:
    """
    1. Save file.
    2. Extract text (PDF/TXT).
    3. LLM Parse to JSON.
    4. Save to Mock/DB.
    """
    # 1. Save File
    file_path = UPLOAD_DIR / f"{session_id}_{file.filename}"
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    logger.info(f"Saved resume to {file_path}")

    # 2. Extract Text
    text_content = ""
    if file.filename.endswith(".pdf"):
        text_content = extract_text_from_pdf(file_path)
    else:
        # Fallback for txt
        try:
            text_content = file_path.read_text(encoding="utf-8")
        except:
            text_content = str(file_path.read_bytes()) # Raw dump if encoding fails

    if len(text_content) < 50:
        raise ValueError("Resume text is too short or unreadable.")

    # 3. LLM Parsing
    prompt_template = load_prompt("parser_resume.md")
    final_prompt = prompt_template.format(resume_text=text_content[:8000]) # Cap length to avoid context error
    
    logger.info("Sending resume text to LLM for parsing...")
    response = await llm.ainvoke([HumanMessage(content=final_prompt)])
    
    # 4. Clean & Validate
    json_str = response.content.replace("```json", "").replace("```", "").strip()
    
    try:
        data = json.loads(json_str)
        
        # Map to Pydantic Schema
        profile = CandidateProfile(
            full_name=data.get("full_name", "Unknown"),
            email=data.get("email"),
            phone=data.get("phone"),
            location=data.get("location"),
            cv_text=text_content, # Important: Store raw text for RAG
            target_roles=data.get("target_roles", []),
            target_keywords=data.get("target_keywords", []),
            skills=data.get("skills", []),
            summary="\n".join(data.get("summary", [])) if isinstance(data.get("summary"), list) else str(data.get("summary", "")),
            experience=data.get("experience", []),
            education=data.get("education", [])
        )

        # 5. Index for RAG (Step 5 Requirement)
        from src.storage.vector_store import create_vector_store
        
        # Create meaningful chunks
        rag_texts = [
           f"Candidate Name: {profile.full_name}\nContact: {profile.email}",
           f"Skills: {', '.join(profile.skills)}",
           f"Summary: {profile.summary}",
           f"Experience: {str(profile.experience)}",
           f"Education: {str(profile.education)}"
        ]
        
        # We assume single-user session for MVP, so we overwrite the index
        logger.info("Indexing resume in Vector Store...")
        create_vector_store(rag_texts, metadatas=[{"source": "resume"}, {"source": "skills"}, {"source": "summary"}, {"source": "experience"}, {"source": "education"}])
        
        return profile, data 
        
    except json.JSONDecodeError:
        logger.error(f"Failed to parse LLM response: {json_str}")
        raise ValueError("AI failed to extract structured data from resume.")
    except ValidationError as e:
        logger.error(f"Validation Error: {e}")
        raise ValueError(f"Extracted data is invalid: {e}")

async def sync_cvs_folder() -> int:
    """
    Scans data/cvs folder for any PDF/TXT files and parses them into MOCK_PROFILES['custom'].
    Returns the number of CVs successfully integrated.
    """
    CV_DIR = Path("data/cvs")
    CV_DIR.mkdir(parents=True, exist_ok=True)
    
    from src.data.mock_profiles import MOCK_PROFILES
    
    count = 0
    # For MVP, we take the LAST found CV as the 'custom' profile
    # In a better version, we'd store all of them or have a switcher
    supported = ["*.pdf", "*.txt"]
    files = []
    for pattern in supported:
        files.extend(list(CV_DIR.glob(pattern)))
    
    if not files:
        logger.info("[parser] No CVs found in data/cvs")
        return 0
    
    # Sort by mtime to get the latest
    files.sort(key=lambda x: x.stat().st_mtime)
    
    for file_path in files:
        # try:
            logger.info(f"[parser] Auto-parsing CV: {file_path.name}")
            
            # Extract
            text_content = ""
            if file_path.suffix.lower() == ".pdf":
                text_content = extract_text_from_pdf(file_path)
            else:
                text_content = file_path.read_text(encoding="utf-8", errors="ignore")
            
            if len(text_content) < 50:
                continue
                
            # Parse via LLM (Async helper)
            prompt_template = load_prompt("parser_resume.md")
            final_prompt = prompt_template.format(resume_text=text_content[:8000])
            
            response = await llm.ainvoke([HumanMessage(content=final_prompt)])
            content = response.content
            
            # Extract JSON more robustly
            import re
            json_match = re.search(r"```json\s*(.*?)\s*```", content, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_str = content.replace("```json", "").replace("```", "").strip()
            
            try:
                data = json.loads(json_str)
            except Exception as je:
                logger.error(f"[parser] JSON decode error for {file_path.name}: {je}")
                logger.debug(f"[parser] Raw content: {content}")
                continue

            if not isinstance(data, dict):
                logger.error(f"[parser] Parsed data is not a dict for {file_path.name}")
                continue
            
            profile = CandidateProfile(
                full_name=data.get("full_name", "Unknown"),
                email=data.get("email"),
                phone=data.get("phone"),
                location=data.get("location"),
                cv_text=text_content,
                skills=data.get("skills", []),
                summary=str(data.get("summary", "")),
                experience=data.get("experience", []),
                education=data.get("education", [])
            )
            
            # Save to store
            MOCK_PROFILES["custom"] = profile
            
            # Also index for RAG
            from src.storage.vector_store import create_vector_store
            rag_texts = [
                f"Candidate: {profile.full_name}",
                f"Skills: {', '.join(profile.skills)}",
                f"Experience: {str(profile.experience)}"
            ]
            create_vector_store(rag_texts)
            
            count += 1
            logger.info(f"[parser] Successfully synced {file_path.name}")
        # except Exception as e:
        #     logger.error(f"[parser] Failed to sync {file_path.name}: {e}")
            
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
