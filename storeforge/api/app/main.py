"""StoreForge API — AI 기반 Shopify 스토어 온보딩 자동화 (Phase 1: 커스텀 앱).

무상태 중계 서버. Shopify 소스코드를 호스팅하거나 동기화하지 않는다 (기획안 §1.2).
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .bootstrap import bootstrap_superadmin
from .config import get_settings
from .db import init_db
from .routers import auth, onboarding, stores


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    bootstrap_superadmin()  # 사용자가 없을 때만 슈퍼어드민 1명 생성
    yield


app = FastAPI(title="StoreForge API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(stores.router)
app.include_router(onboarding.router)


@app.get("/health")
def health() -> dict:
    return {"ok": True}
