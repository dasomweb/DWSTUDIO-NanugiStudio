"""비밀번호 해시, JWT, Shopify 토큰 암호화."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from cryptography.fernet import Fernet, InvalidToken

from .config import get_settings


# --- 비밀번호 ------------------------------------------------------------------
def hash_password(raw: str) -> str:
    return bcrypt.hashpw(raw.encode(), bcrypt.gensalt()).decode()


def verify_password(raw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(raw.encode(), hashed.encode())
    except ValueError:
        return False


# --- JWT ----------------------------------------------------------------------
def create_access_token(user_id: int, role: str) -> str:
    s = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=s.access_token_ttl_minutes),
    }
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm)


def decode_access_token(token: str) -> dict | None:
    s = get_settings()
    try:
        return jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_algorithm])
    except jwt.PyJWTError:
        return None


# --- Shopify Admin API 토큰 ------------------------------------------------------
def _fernet() -> Fernet:
    return Fernet(get_settings().token_encryption_key.encode())


def encrypt_token(raw: str) -> str:
    return _fernet().encrypt(raw.encode()).decode()


def decrypt_token(enc: str) -> str:
    try:
        return _fernet().decrypt(enc.encode()).decode()
    except InvalidToken as exc:
        # 암호화 키가 바뀌었거나 DB 가 다른 환경에서 온 경우. 조용히 실패시키면 안 된다.
        raise RuntimeError(
            "Shopify 토큰 복호화 실패 — STOREFORGE_TOKEN_ENCRYPTION_KEY 가 저장 시점과 다릅니다."
        ) from exc


def mask_token(raw: str) -> str:
    if len(raw) <= 8:
        return "•" * len(raw)
    return f"{raw[:6]}…{raw[-4:]}"
