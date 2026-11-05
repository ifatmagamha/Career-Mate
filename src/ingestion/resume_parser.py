"""CV upload: validate the file, extract its text, parse it with the LLM. The profile and the file itself are
stored per user in the database (profiles table), so nothing depends on the server's disk."""
import io
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from fastapi import UploadFile

from src.config.logging import logger
from src.schemas.candidate import CandidateProfile
from src.agents.parser import parse_resume_text, map_parsed_to_profile
from src.storage import db

MIME = {".pdf": "application/pdf", ".txt": "text/plain"}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


async def read_upload(file: UploadFile) -> Tuple[str, bytes]:
    """(bare file name, content) after checking type and size. Nothing is parsed yet."""
    name = Path(file.filename or "").name  # the name comes from the browser: keep the bare name only
    if Path(name).suffix.lower() not in MIME:
        raise ValueError("Upload a PDF or TXT file.")
    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise ValueError("File too large (max 10 MB).")
    return name, content


def parse_cv(name: str, content: bytes) -> Tuple[CandidateProfile, Dict[str, Any]]:
    """Extract the text and parse it into a profile (one LLM call)."""
    text = extract_text_from_pdf(content) if name.lower().endswith(".pdf") else content.decode("utf-8", errors="ignore")
    if len(text) < 50:
        raise ValueError("Resume text is too short or unreadable (scanned PDF without text?).")
    logger.info("[parser] Segmenting and classifying resume text...")
    parsed = parse_resume_text(text)
    if not parsed:
        raise ValueError("AI failed to extract structured data from resume.")
    return map_parsed_to_profile(parsed, text), parsed


def save_cv(conn, user_id: str, profile: CandidateProfile, name: str, content: bytes) -> None:
    db.save_profile(conn, user_id, profile.model_dump(), source_file=name, cv_file=content,
                    cv_mime=MIME[Path(name).suffix.lower()])


def load_saved_profile(conn, user_id: str) -> Optional[CandidateProfile]:
    saved = db.get_profile(conn, user_id)
    return CandidateProfile.model_validate(saved["profile"]) if saved else None


def extract_text_from_pdf(content: bytes) -> str:
    try:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(content))
        return "\n".join(page.extract_text() or "" for page in reader.pages).strip()
    except Exception as e:
        logger.error(f"PDF Extraction Error: {e}")
        return ""


if __name__ == "__main__":
    import asyncio
    import uuid
    from starlette.datastructures import UploadFile as StarletteUpload

    def upload(name, data=b"x"):
        return asyncio.run(read_upload(StarletteUpload(io.BytesIO(data), filename=name)))

    # upload validation runs before any LLM call
    for bad in ("cv.docx", "cv.exe"):
        try:
            upload(bad)
            raise AssertionError("expected ValueError")
        except ValueError as e:
            assert "PDF or TXT" in str(e)
    try:
        upload("cv.pdf", b"0" * (MAX_UPLOAD_BYTES + 1))
        raise AssertionError("expected ValueError")
    except ValueError as e:
        assert "too large" in str(e)
    assert upload("../../evil.txt", b"short") == ("evil.txt", b"short")  # path parts dropped
    try:
        parse_cv("evil.txt", b"short")
        raise AssertionError("expected ValueError")
    except ValueError as e:
        assert "too short" in str(e)
    assert extract_text_from_pdf(b"not a pdf") == ""

    U = str(uuid.uuid4())
    with db.temp_schema() as c:
        assert load_saved_profile(c, U) is None
        p = CandidateProfile(full_name="Ada", skills=["SQL"], cv_text="x")
        save_cv(c, U, p, "cv.pdf", b"%PDF-1.4")
        db.save_profile(c, U, p.model_copy(update={"skills": ["SQL", "dbt"]}).model_dump())  # edit keeps the file
        assert load_saved_profile(c, U).skills == ["SQL", "dbt"]
        f = db.get_cv_file(c, U)
        assert (f["source_file"], f["cv_file"], f["cv_mime"]) == ("cv.pdf", b"%PDF-1.4", "application/pdf")
    print("resume_parser ok")
