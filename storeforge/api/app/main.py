"""StoreForge API — AI 기반 Shopify 스토어 온보딩 자동화 (Phase 1: 커스텀 앱).

무상태 중계 서버. Shopify 소스코드를 호스팅하거나 동기화하지 않는다 (기획안 §1.2).
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session

from .bootstrap import bootstrap_superadmin
from .config import get_settings
from .db import engine, init_db
from .routers import auth, listpilot, onboarding, pricewave, stores, themes

log = logging.getLogger(__name__)


async def _pricewave_loop(interval_seconds: int) -> None:
    """Pricewave 를 켠 스토어들의 활성 할인을 주기적으로 샵 메타필드에 반영한다.

    머천트가 Shopify Admin 에서 할인을 만들거나 끝내는 것을 우리가 알 방법이 없으므로
    (웹훅을 붙이기 전까지는) 주기적으로 다시 읽는다. 실패해도 루프는 죽지 않는다 —
    여기서 죽으면 그 뒤로 영영 동기화되지 않는데, 그건 조용히 낡은 세일가를 보여주는 것이라
    더 나쁘다.
    """
    while True:
        try:
            with Session(engine) as session:
                await pricewave.sync_all(session)
        except Exception as exc:  # noqa: BLE001 — 루프를 살려 두는 것이 목적이다
            log.warning("[pricewave] 동기화 루프 오류: %s", exc)
        await asyncio.sleep(interval_seconds)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    bootstrap_superadmin()  # 사용자가 없을 때만 슈퍼어드민 1명 생성

    task: asyncio.Task | None = None
    interval = get_settings().pricewave_sync_seconds
    if interval > 0:
        task = asyncio.create_task(_pricewave_loop(interval))
        log.info("[pricewave] %d초 주기 동기화 시작", interval)

    yield

    if task:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


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
app.include_router(pricewave.router)
app.include_router(listpilot.router)
app.include_router(themes.router)


@app.get("/health")
def health() -> dict:
    return {"ok": True}
