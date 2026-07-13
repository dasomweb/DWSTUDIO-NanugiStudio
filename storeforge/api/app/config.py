"""환경 설정."""

from __future__ import annotations

import os
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 인증
    jwt_secret: str = Field(default="dev-only-change-me")
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 60 * 12

    # Shopify Admin API 토큰(shpat_…)을 DB 에 평문 저장하지 않는다.
    # 이 키가 유출되면 연동된 모든 스토어가 열린다 — 프로덕션에서는 반드시 주입할 것.
    token_encryption_key: str = Field(default="")

    # Shopify
    shopify_api_version: str = "2025-01"  # 기획안 §8: 버전 고정 + 분기별 changelog 점검

    # 축① 브랜드 해석. 비워두면 SDK 가 ANTHROPIC_API_KEY 등 표준 경로에서 찾는다.
    anthropic_api_key: str = ""

    database_url: str = "sqlite:///./storeforge.db"
    cors_origins: str = "http://localhost:3000"

    class Config:
        env_file = ".env"
        env_prefix = "STOREFORGE_"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    if not s.token_encryption_key:
        # 개발 편의: 키가 없으면 로컬 파일에 하나 만들어 재사용한다.
        # 프로덕션에서는 STOREFORGE_TOKEN_ENCRYPTION_KEY 를 반드시 주입해야 한다.
        from cryptography.fernet import Fernet

        path = ".dev-encryption-key"
        if os.path.exists(path):
            key = open(path).read().strip()
        else:
            key = Fernet.generate_key().decode()
            with open(path, "w") as f:
                f.write(key)
        s.token_encryption_key = key
    return s
