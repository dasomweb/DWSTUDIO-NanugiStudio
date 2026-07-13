"""환경 설정.

프로덕션(STOREFORGE_ENV=production)에서는 비밀값을 자동 생성하지 않는다.
자동 생성은 개발 편의 기능이며, 프로덕션에서 이게 동작하면 재배포마다 키가 바뀌어
저장된 Shopify 토큰을 전부 복호화할 수 없게 된다. 그래서 켜지지 않고 죽는다.
"""

from __future__ import annotations

import os
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings

DEV_KEY_FILE = ".dev-encryption-key"


class Settings(BaseSettings):
    env: str = "development"  # development | production

    # 인증
    jwt_secret: str = Field(default="")
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 60 * 12

    # Shopify Admin API 토큰(shpat_…)을 DB 에 평문 저장하지 않는다.
    # 이 키가 유출되면 연동된 모든 스토어가 열린다.
    token_encryption_key: str = Field(default="")

    # Shopify
    shopify_api_version: str = "2025-01"  # 기획안 §8: 버전 고정 + 분기별 changelog 점검

    # 축① 브랜드 해석. 비워두면 SDK 가 ANTHROPIC_API_KEY 등 표준 경로에서 찾는다.
    anthropic_api_key: str = ""

    # Pricewave 할인 동기화 주기. 0 이면 백그라운드 루프를 돌리지 않는다.
    # 머천트가 Shopify Admin 에서 할인을 켜고 끄는 것을 알 방법이 (웹훅 전까지) 없어서 폴링한다.
    pricewave_sync_seconds: int = 300

    database_url: str = ""
    cors_origins: str = "http://localhost:3000"

    class Config:
        env_file = ".env"
        env_prefix = "STOREFORGE_"
        extra = "ignore"

    @property
    def is_production(self) -> bool:
        return self.env.lower() == "production"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


def _resolve_database_url(configured: str) -> str:
    """Railway 는 Postgres 를 붙이면 DATABASE_URL 을 자동 주입한다.

    SQLAlchemy 는 `postgres://` 스킴을 모른다 — `postgresql://` 로 바꿔줘야 한다.
    (Railway/Heroku 가 주는 URL 이 옛 스킴인 경우가 있어 여기서 흡수한다.)
    """
    url = configured or os.getenv("DATABASE_URL", "")
    if not url:
        return "sqlite:///./storeforge.db"  # 로컬 개발 전용

    # 스킴 정규화. psycopg3 를 쓰므로 드라이버를 명시해야 한다 —
    # 그냥 postgresql:// 로 두면 SQLAlchemy 가 psycopg2 를 찾다가 죽는다.
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def _dev_secret(name: str, generator) -> str:
    """개발 환경에서만 쓰는 비밀값 자동 생성. 파일에 캐시해 재시작해도 유지한다."""
    path = f"{DEV_KEY_FILE}.{name}"
    if os.path.exists(path):
        return open(path).read().strip()
    value = generator()
    with open(path, "w") as f:
        f.write(value)
    return value


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.database_url = _resolve_database_url(s.database_url)

    missing = [
        name
        for name, value in (
            ("STOREFORGE_JWT_SECRET", s.jwt_secret),
            ("STOREFORGE_TOKEN_ENCRYPTION_KEY", s.token_encryption_key),
        )
        if not value
    ]

    if s.is_production:
        if missing:
            # 여기서 죽는 게 맞다. 자동 생성된 키로 뜨면 재배포 시점에
            # 저장된 Shopify 토큰이 전부 복호화 불가가 된다.
            raise RuntimeError(
                "프로덕션에 필수 비밀값이 없습니다: "
                + ", ".join(missing)
                + " — Railway 환경변수에 주입하세요."
            )
        if s.database_url.startswith("sqlite"):
            # Railway 컨테이너 파일시스템은 휘발성이다. 재배포하면 DB 가 사라진다.
            raise RuntimeError(
                "프로덕션에서 SQLite 를 쓸 수 없습니다 — Postgres 를 연결하고 DATABASE_URL 을 주입하세요."
            )
        return s

    # --- 개발 환경 ---
    from cryptography.fernet import Fernet
    from secrets import token_urlsafe

    if not s.jwt_secret:
        s.jwt_secret = _dev_secret("jwt", lambda: token_urlsafe(32))
    if not s.token_encryption_key:
        s.token_encryption_key = _dev_secret("fernet", lambda: Fernet.generate_key().decode())
    return s
