import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from fastapi import UploadFile

from src.config.logging import logger
from src.config.settings import settings
from src.schemas.candidate import CandidateProfile
from src.agents.parser import parse_resume_text, map_parsed_to_profile
from src.storage.vector_store import create_vector_store, get_vector_store

CV_DIR = Path(settings.DATA_DIR) / "cvs"                 # saved CV files (git-ignored)
PROFILE_PATH = Path(settings.DATA_DIR) / "profile.json"  # parsed profile, reloaded at startup without the LLM
ALLOWED_SUFFIXES = {".pdf", ".txt"}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


async def handle_resume_upload(file: UploadFile) -> Tuple[CandidateProfile, Dict[str, Any]]:
    """
    1. Validate and save the file in data/cvs.
    2. Extract text (PDF/TXT).
    3. LLM Parse to JSON via specialized Parser Agent.
    4. Save the profile, index it for RAG.
    """
    # 1. Validate + save (the filename comes from the browser: keep the bare name only)
    name = Path(file.filename or "").name
    if Path(name).suffix.lower() not in ALLOWED_SUFFIXES:
        raise ValueError("Upload a PDF or TXT file.")
    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise ValueError("File too large (max 10 MB).")
    CV_DIR.mkdir(parents=True, exist_ok=True)
    file_path = CV_DIR / name
    file_path.write_bytes(content)
    logger.info(f"[parser] Saved resume to {file_path}")

    # 2-4
    profile, parsed_data = parse_cv_file(file_path)
    return profile, parsed_data


def parse_cv_file(file_path: Path) -> Tuple[CandidateProfile, Dict[str, Any]]:
    """Extract text, parse with the LLM, save the profile and index it."""
    text_content = extract_text_from_pdf(file_path) if file_path.suffix.lower() == ".pdf" \
        else file_path.read_text(encoding="utf-8", errors="ignore")
    if len(text_content) < 50:
        raise ValueError("Resume text is too short or unreadable (scanned PDF without text?).")

    logger.info("[parser] Segmenting and classifying resume text...")
    parsed_data = parse_resume_text(text_content)
    if not parsed_data:
        raise ValueError("AI failed to extract structured data from resume.")

    profile = map_parsed_to_profile(parsed_data, text_content)
    save_profile(profile, source_file=file_path.name)
    index_profile_for_rag(profile)
    return profile, parsed_data


def save_profile(profile: CandidateProfile, source_file: Optional[str] = None) -> None:
    previous = _read_saved()
    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROFILE_PATH.write_text(json.dumps({
        "source_file": source_file or (previous or {}).get("source_file"),
        "saved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "profile": profile.model_dump(),
    }, ensure_ascii=False, indent=2), encoding="utf-8")


def load_saved_profile() -> Optional[CandidateProfile]:
    saved = _read_saved()
    return CandidateProfile.model_validate(saved["profile"]) if saved else None


def _read_saved() -> Optional[Dict[str, Any]]:
    try:
        return json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


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


def restore_profile() -> Optional[CandidateProfile]:
    """Startup: reload the saved profile (no LLM call). Parse the latest CV only if nothing was saved yet."""
    profile = load_saved_profile()
    if profile:
        if get_vector_store() is None:  # missing index, or built with another embedding model
            index_profile_for_rag(profile)
        return profile
    latest = _latest_cv()
    return parse_cv_file(latest)[0] if latest else None


async def sync_cvs_folder() -> int:
    """Manual sync: re-parse the most recent CV in data/cvs (replaces the saved profile)."""
    from src.data.mock_profiles import MOCK_PROFILES

    latest = _latest_cv()
    if not latest:
        return 0
    MOCK_PROFILES["custom"] = parse_cv_file(latest)[0]
    logger.info(f"[sync] Processed {latest.name}")
    return 1


def _latest_cv() -> Optional[Path]:
    files = [p for p in CV_DIR.glob("*") if p.suffix.lower() in ALLOWED_SUFFIXES] if CV_DIR.exists() else []
    return max(files, key=lambda p: p.stat().st_mtime) if files else None


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


if __name__ == "__main__":
    import asyncio
    import io
    import tempfile
    from starlette.datastructures import UploadFile as StarletteUpload

    with tempfile.TemporaryDirectory() as d:
        PROFILE_PATH = Path(d) / "profile.json"
        CV_DIR = Path(d) / "cvs"
        assert load_saved_profile() is None

        p = CandidateProfile(full_name="Ada", skills=["SQL"], cv_text="x")
        save_profile(p, source_file="cv.pdf")
        save_profile(p.model_copy(update={"skills": ["SQL", "dbt"]}))  # edit keeps the source file
        saved = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
        assert saved["source_file"] == "cv.pdf" and load_saved_profile().skills == ["SQL", "dbt"]

        # upload validation runs before any LLM call
        def upload(name, data=b"x"):
            return asyncio.run(handle_resume_upload(StarletteUpload(io.BytesIO(data), filename=name)))
        for bad, msg in [("cv.docx", "PDF or TXT"), ("cv.exe", "PDF or TXT")]:
            try:
                upload(bad)
                raise AssertionError("expected ValueError")
            except ValueError as e:
                assert msg in str(e)
        try:
            upload("cv.pdf", b"0" * (MAX_UPLOAD_BYTES + 1))
            raise AssertionError("expected ValueError")
        except ValueError as e:
            assert "too large" in str(e)
        try:  # path traversal: the file lands inside CV_DIR, then the short text is rejected before the LLM
            upload("../../evil.txt", b"short")
        except ValueError as e:
            assert "too short" in str(e)
        assert (CV_DIR / "evil.txt").exists() and not (Path(d).parent / "evil.txt").exists()
        assert _latest_cv() == CV_DIR / "evil.txt"
    print("resume_parser ok")
