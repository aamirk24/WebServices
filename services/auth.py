from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import get_settings

settings = get_settings()

pwd_context = CryptContext(schemes=["bcrypt_sha256"], deprecated="auto")

ACCESS_TOKEN_EXPIRE_MINUTES = settings.access_token_expire_minutes
REFRESH_TOKEN_EXPIRE_DAYS = 7


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(
    data: dict[str, Any],
    expires_delta: timedelta | None = None,
) -> str:
    to_encode = data.copy()
    expire = datetime.now(UTC) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update(
        {
            "exp": expire,
            "type": "access",
        }
    )
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def create_refresh_token(data: dict[str, Any]) -> str:
    to_encode = data.copy()
    expire = datetime.now(UTC) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update(
        {
            "exp": expire,
            "type": "refresh",
        }
    )
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def decode_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
        )
        return payload
    except JWTError as exc:
        raise ValueError("Invalid or expired token") from exc


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def generate_api_key() -> tuple[str, str]:
    """
    Generate a new API key and return:
    (raw_key, key_hash)

    raw_key:
        shown once to the user and never stored
    key_hash:
        stored in the database
    """
    raw_key = secrets.token_urlsafe(32)
    key_hash = hash_api_key(raw_key)
    return raw_key, key_hash


def verify_api_key(raw_key: str, stored_hash: str) -> bool:
    return hash_api_key(raw_key) == stored_hash