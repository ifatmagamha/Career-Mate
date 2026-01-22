# src/storage/user_store.py
from __future__ import annotations

import json
import os
import secrets
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

from src.config.settings import settings
from src.schemas.user import UserProfile


def _utc_now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _data_dir() -> Path:
    return Path(settings.DATA_DIR)


def _users_dir() -> Path:
    p = _data_dir() / "users"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _auth_path() -> Path:
    # single file mapping email -> {user_id, salt, hash}
    p = _data_dir() / "auth.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists():
        p.write_text(json.dumps({}, indent=2), encoding="utf-8")
    return p


# --- Password hashing (PBKDF2-HMAC-SHA256) ---
def _hash_password(password: str, salt_hex: str) -> str:
    salt = bytes.fromhex(salt_hex)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
    return dk.hex()


def _new_salt_hex() -> str:
    return secrets.token_bytes(16).hex()


def _load_auth() -> Dict[str, Any]:
    p = _auth_path()
    return json.loads(p.read_text(encoding="utf-8"))


def _save_auth(d: Dict[str, Any]) -> None:
    p = _auth_path()
    p.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


def _email_key(email: str) -> str:
    return email.strip().lower()


def _user_path(user_id: str) -> Path:
    return _users_dir() / f"{user_id}.json"


def create_user(email: str, password: str) -> UserProfile:
    email_k = _email_key(email)
    auth = _load_auth()
    if email_k in auth:
        raise ValueError("Email already registered")

    user_id = secrets.token_hex(16)
    salt = _new_salt_hex()
    pw_hash = _hash_password(password, salt)

    auth[email_k] = {"user_id": user_id, "salt": salt, "hash": pw_hash}
    _save_auth(auth)

    profile = UserProfile(
        user_id=user_id,
        email=email_k,
        full_name="",
        location="Paris",
        created_at=_utc_now(),
        updated_at=_utc_now(),
    )
    save_profile(profile)
    return profile


def authenticate(email: str, password: str) -> Tuple[str, UserProfile]:
    email_k = _email_key(email)
    auth = _load_auth()
    rec = auth.get(email_k)
    if not rec:
        raise ValueError("Invalid credentials")

    salt = rec["salt"]
    expected = rec["hash"]
    got = _hash_password(password, salt)
    if not secrets.compare_digest(got, expected):
        raise ValueError("Invalid credentials")

    user_id = rec["user_id"]
    profile = load_profile(user_id)
    return user_id, profile


def load_profile(user_id: str) -> UserProfile:
    p = _user_path(user_id)
    if not p.exists():
        raise FileNotFoundError("User profile not found")
    data = json.loads(p.read_text(encoding="utf-8"))
    return UserProfile.model_validate(data)


def save_profile(profile: UserProfile) -> None:
    profile.updated_at = _utc_now()
    p = _user_path(profile.user_id)
    p.write_text(json.dumps(profile.model_dump(mode="json"), ensure_ascii=False, indent=2), encoding="utf-8")


def get_profile_by_email(email: str) -> Optional[UserProfile]:
    email_k = _email_key(email)
    auth = _load_auth()
    rec = auth.get(email_k)
    if not rec:
        return None
    return load_profile(rec["user_id"])
