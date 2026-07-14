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

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
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


def _proxy_zip_url(request: Request) -> str:
    """themeCreate 에 넘길 zip URL — 우리 API 의 프록시 주소.

    GitHub 의 releases/latest/download/… 는 302 리다이렉트인데, Shopify themeCreate 는
    리다이렉트를 따라가지 않고 "Src must be a zip file" 로 거부한다. 그래서 GitHub 원본을
    직접 주지 않고, 우리가 200 으로 스트리밍해 주는 아래 /themes/source.zip 을 준다.
    """
    base = str(request.base_url).rstrip("/")
    # Railway 프록시 뒤에서는 base_url 이 http 로 잡힌다. Shopify 는 https 만 받는다.
    if base.startswith("http://") and "localhost" not in base and "127.0.0.1" not in base:
        base = "https://" + base[len("http://"):]
    return f"{base}/themes/source.zip"


@router.get("/source")
def theme_source(request: Request, _: User = Depends(current_user)) -> dict:
    """설치에 실제로 쓰이는 zip URL(프록시)과 그 원본. 화면이 설치 카드에 보여준다."""
    return {"zip_url": _proxy_zip_url(request), "upstream": get_settings().theme_zip_url}


@router.get("/source.zip")
async def source_zip() -> Response:
    """소스 테마 zip 을 200 으로 직접 스트리밍한다.

    인증이 없는 것은 의도다 — Shopify 서버가 이 URL 을 직접 가져가야 하기 때문이다.
    내용은 공개 저장소의 릴리즈 자산이므로 새는 것이 없다. URL 은 설정 고정값만 쓰므로
    SSRF 여지도 없다.
    """
    upstream = get_settings().theme_zip_url
    async with httpx.AsyncClient(follow_redirects=True, timeout=120) as client:
        resp = await client.get(upstream)
    if resp.status_code >= 400:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            f"소스 zip 을 가져오지 못했습니다 (upstream HTTP {resp.status_code}): {upstream}",
        )
    return Response(
        content=resp.content,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="theme.zip"'},
    )


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
async def install(
    body: InstallIn, request: Request, store: Store = Depends(get_store)
) -> InstallOut:
    """소스 테마를 이 스토어에 설치한다.

    기존 테마는 건드리지 않는다 — 새 테마가 하나 늘고, publish=True 면 그걸 라이브로
    올린다(기존 라이브는 unpublished 로 내려간다). 잘못돼도 이전 테마로 되돌릴 수 있다.
    """
    _guard(store)

    zip_url = body.zip_url or _proxy_zip_url(request)
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
