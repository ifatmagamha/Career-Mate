# src/agents/tracker.py
from __future__ import annotations

import json
import os
from datetime import datetime
from typing import List, Optional

from src.config.logging import logger
from src.schemas.job_offer import OfferAnalyzed
from src.schemas.tracker import (
    ApplicationRecord,
    ApplicationStatus,
    ApplicationEvent,
    TrackingDB,
)


DEFAULT_TRACKING_PATH = "data/tracking.json"


def _now() -> str:
    return datetime.utcnow().isoformat()


def _load_db(path: str) -> TrackingDB:
    if not os.path.exists(path):
        return TrackingDB()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return TrackingDB.model_validate(data)
    except Exception as e:
        logger.warning(f"[tracker] failed to load db path={path} err={e}")
        return TrackingDB()


def _save_db(path: str, db: TrackingDB) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(db.model_dump(mode="json"), f, ensure_ascii=False, indent=2)


def _find_record(records: List[ApplicationRecord], offer_url: str) -> Optional[ApplicationRecord]:
    for r in records:
        if str(r.offer_url) == str(offer_url):
            return r
    return None


def upsert_application(
    user_id: str,
    offer: OfferAnalyzed,
    cv_pdf: Optional[str] = None,
    letter_pdf: Optional[str] = None,
    status: ApplicationStatus = "to_apply",
    tracking_path: str = DEFAULT_TRACKING_PATH,
) -> ApplicationRecord:
    """
    Create application record if missing, else update pdf paths/status.
    """
    db = _load_db(tracking_path)
    records = db.applications.get(user_id, [])

    existing = _find_record(records, str(offer.url))
    if existing is None:
        rec = ApplicationRecord(
            user_id=user_id,
            offer_url=str(offer.url),
            offer_title=offer.title,
            company=offer.company,
            location=offer.location,
            status=status,
            cv_pdf=cv_pdf,
            letter_pdf=letter_pdf,
            created_at=_now(),
            updated_at=_now(),
            notes=[],
            events=[ApplicationEvent(action="created", meta={"status": status})],
        )
        records.append(rec)
        db.applications[user_id] = records
        _save_db(tracking_path, db)
        logger.info(f"[tracker] created application user={user_id} url={offer.url}")
        return rec

    # Update existing
    changed = False
    if cv_pdf and existing.cv_pdf != cv_pdf:
        existing.cv_pdf = cv_pdf
        changed = True
    if letter_pdf and existing.letter_pdf != letter_pdf:
        existing.letter_pdf = letter_pdf
        changed = True
    if status and existing.status != status:
        existing.status = status
        existing.events.append(ApplicationEvent(action="status_changed", meta={"status": status}))
        changed = True

    if changed:
        existing.updated_at = _now()
        _save_db(tracking_path, db)
        logger.info(f"[tracker] updated application user={user_id} url={offer.url}")

    return existing


def add_note(
    user_id: str,
    offer_url: str,
    note: str,
    tracking_path: str = DEFAULT_TRACKING_PATH,
) -> None:
    db = _load_db(tracking_path)
    records = db.applications.get(user_id, [])
    rec = _find_record(records, offer_url)
    if rec is None:
        raise ValueError("Application not found for this offer_url")

    note = (note or "").strip()
    if note:
        rec.notes.append(note)
        rec.events.append(ApplicationEvent(action="note_added", meta={"note": note[:120]}))
        rec.updated_at = _now()
        _save_db(tracking_path, db)
        logger.info(f"[tracker] note added user={user_id} url={offer_url}")


def list_applications(user_id: str, tracking_path: str = DEFAULT_TRACKING_PATH) -> List[ApplicationRecord]:
    db = _load_db(tracking_path)
    return db.applications.get(user_id, [])
