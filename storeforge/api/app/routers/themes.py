"""테마 설치 — 소스 테마 zip → 고객 스토어 (기획안 §6.3).

고객 스토어에는 GitHub Actions 로 배포하지 않는다. 소스 저장소의 릴리즈 zip 을
themeCreate 로 넣어 **GitHub 미연동 테마**를 만든다. 에디터 수정이 저장소로 역류하지
않고, 스토어별 설정(색·배치·콘텐츠)이 서로 섞이지 않는 것이 이 경로의 존재 이유다.

브랜드 색상 차이는 테마 파일이 아니라 metafield 주입(축①)으로 해결하므로,
설치되는 zip 은 모든 스토어에 동일하다.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ..config import get_settings
from ..deps import current_user, get_store
from ..models import Store, User
from ..routers.stores import client_for
from ..shopify import ShopifyError

router = APIRouter(prefix="/themes", tags=["themes"])
log = logging.getLogger(__name__)


class InstallIn(BaseModel):
    publish: bool = True
    name: str | None = None  # 비우면 "DWSTUDIO vX (스토어명)" 형태로 서버가 정한다
    zip_url: str | None = None  # 비우면 설정의 기본 zip (latest 릴리즈)


class InstallOut(BaseModel):
    theme_gid: str
    theme_name: str
    published: bool
    zip_url: str
    installed_at: datetime


@router.get("/source")
def theme_source(_: User = Depends(current_user)) -> dict:
    """기본 소스 zip URL. 화면이 설치 카드에 보여준다."""
    return {"zip_url": get_settings().theme_zip_url}


def _guard(store: Store) -> None:
    # themeCreate/themePublish 는 write_themes 를 요구한다. 모듈 토글이 아니라 스코프를
    # 직접 본다 — 테마 설치는 특정 모듈의 기능이 아니라 온보딩의 전제 단계이기 때문이다.
    if not store.connected:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "스토어 연결이 확인되지 않았습니다. 먼저 연결 테스트를 통과시키세요.",
        )
    if store.granted_scopes and "write_themes" not in store.scope_list:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "write_themes 스코프가 없어 테마를 설치할 수 없습니다 — Dev Dashboard 에서 스코프를 "
            "추가해 새 버전을 Release 하고 앱을 재설치한 뒤 연결 테스트를 다시 하세요.",
        )


@router.post("/stores/{store_id}/install", response_model=InstallOut)
async def install(body: InstallIn, store: Store = Depends(get_store)) -> InstallOut:
    """소스 테마를 이 스토어에 설치한다.

    기존 테마는 건드리지 않는다 — 새 테마가 하나 늘고, publish=True 면 그걸 라이브로
    올린다(기존 라이브는 unpublished 로 내려간다). 잘못돼도 이전 테마로 되돌릴 수 있다.
    """
    _guard(store)

    zip_url = body.zip_url or get_settings().theme_zip_url
    name = body.name or f"DWSTUDIO — {store.name}"

    try:
        client = await client_for(store)
        theme = await client.theme_create(zip_url, name)
        # zip 을 Shopify 가 비동기로 푼다. 끝나기 전에 발행하면 빈 테마가 라이브에 올라간다.
        await client.theme_wait_ready(theme["id"])
        if body.publish:
            await client.theme_publish(theme["id"])
    except ShopifyError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

    log.info("[themes] %s: '%s' 설치 (publish=%s)", store.shop_domain, name, body.publish)
    return InstallOut(
        theme_gid=theme["id"],
        theme_name=name,
        published=body.publish,
        zip_url=zip_url,
        installed_at=datetime.now(timezone.utc),
    )
