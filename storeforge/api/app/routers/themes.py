"""테마 설치 — 소스 테마 릴리즈 → 스토어 (기획안 §6.3).

고객 스토어에는 GitHub Actions 로 배포하지 않는다. 릴리즈의 theme.zip 을 themeCreate 로
넣어 **GitHub 미연동 테마**를 만든다. 에디터 수정이 저장소로 역류하지 않고, 스토어별
설정(색·배치·콘텐츠)이 서로 섞이지 않는 것이 이 경로의 존재 이유다.

버전 격리: 릴리즈(v* 태그)가 소스 테마의 버전이고, 각 스토어는 **자기 시점에 원하는
버전을 골라** 설치한다. 설치된 버전은 Store.installed_theme_version 에 남는다 —
새 릴리즈가 나와도 스토어가 저절로 바뀌는 일은 없다.

브랜드 색상 차이는 테마 파일이 아니라 metafield 주입(축①)으로 해결하므로,
같은 버전의 zip 은 모든 스토어에 동일하다.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel
from sqlmodel import Session

from ..config import get_settings
from ..db import get_session
from ..deps import current_user, get_store
from ..models import Store, User
from ..routers.stores import client_for
from ..shopify import ShopifyError

router = APIRouter(prefix="/themes", tags=["themes"])
log = logging.getLogger(__name__)

# 릴리즈 태그 형식. URL 조립에 들어가므로 여기서 걸러 SSRF 여지를 없앤다.
_VERSION_RE = re.compile(r"^v[\w.\-]+$")


class InstallIn(BaseModel):
    publish: bool = True
    version: str | None = None  # 릴리즈 태그 (예: v1.1.0). 비우면 latest
    name: str | None = None  # 비우면 "DWSTUDIO vX (스토어명)" 형태로 서버가 정한다


class InstallOut(BaseModel):
    theme_gid: str
    theme_name: str
    published: bool
    version: str  # 실제로 설치된 릴리즈 태그
    installed_at: datetime


def _check_version(version: str | None) -> str | None:
    if version and not _VERSION_RE.match(version):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"올바른 버전 태그가 아닙니다: {version!r}")
    return version


async def _latest_release_tag() -> str | None:
    """latest 릴리즈의 실제 태그. '최신'이라는 말 대신 정확한 버전을 스토어에 기록하기 위해서다."""
    repo = get_settings().theme_release_repo
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"https://api.github.com/repos/{repo}/releases/latest",
                headers={"Accept": "application/vnd.github+json"},
            )
        if resp.status_code == 200:
            return resp.json().get("tag_name")
    except httpx.HTTPError:
        pass
    return None


def _proxy_zip_url(request: Request, version: str | None) -> str:
    """themeCreate 에 넘길 zip URL — 우리 API 의 프록시 주소.

    GitHub 릴리즈 다운로드는 302 리다이렉트인데, Shopify themeCreate 는 리다이렉트를
    따라가지 않고 "Src must be a zip file" 로 거부한다. 그래서 GitHub 원본을 직접 주지
    않고, 우리가 200 으로 스트리밍해 주는 /themes/source.zip 을 준다.
    """
    base = str(request.base_url).rstrip("/")
    # Railway 프록시 뒤에서는 base_url 이 http 로 잡힌다. Shopify 는 https 만 받는다.
    if base.startswith("http://") and "localhost" not in base and "127.0.0.1" not in base:
        base = "https://" + base[len("http://"):]
    url = f"{base}/themes/source.zip"
    if version:
        url += f"?version={version}"
    return url


@router.get("/source")
async def theme_source(request: Request, _: User = Depends(current_user)) -> dict:
    """설치에 쓰이는 zip URL(프록시), 원본, 그리고 latest 가 가리키는 실제 태그."""
    settings = get_settings()
    return {
        "zip_url": _proxy_zip_url(request, None),
        "upstream": settings.theme_zip_upstream(),
        "latest_version": await _latest_release_tag(),
    }


@router.get("/source.zip")
async def source_zip(version: str | None = None) -> Response:
    """소스 테마 zip 을 200 으로 직접 스트리밍한다.

    인증이 없는 것은 의도다 — Shopify 서버가 이 URL 을 직접 가져가야 하기 때문이다.
    내용은 공개 저장소의 릴리즈 자산이므로 새는 것이 없고, version 은 태그 형식만
    통과시키므로 SSRF 여지도 없다.
    """
    _check_version(version)
    upstream = get_settings().theme_zip_upstream(version)
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
    body: InstallIn,
    request: Request,
    store: Store = Depends(get_store),
    session: Session = Depends(get_session),
) -> InstallOut:
    """소스 테마를 이 스토어에 설치한다.

    기존 테마는 건드리지 않는다 — 새 테마가 하나 늘고, publish=True 면 그걸 라이브로
    올린다(기존 라이브는 unpublished 로 내려간다). 잘못돼도 이전 테마로 되돌릴 수 있다.
    """
    _guard(store)
    _check_version(body.version)

    # "latest" 로 설치해도 기록은 정확한 태그로 남긴다. 나중에 "이 스토어 어떤 버전이지?"
    # 에 '그때의 최신'이라고 답할 수는 없다.
    version = body.version or await _latest_release_tag()
    zip_url = _proxy_zip_url(request, body.version)
    name = body.name or f"DWSTUDIO {version or ''} — {store.name}".replace("  ", " ")

    try:
        client = await client_for(store)
        theme = await client.theme_create(zip_url, name)
        # zip 을 Shopify 가 비동기로 푼다. 끝나기 전에 발행하면 빈 테마가 라이브에 올라간다.
        await client.theme_wait_ready(theme["id"])
        if body.publish:
            await client.theme_publish(theme["id"])
    except ShopifyError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

    now = datetime.now(timezone.utc)
    store.installed_theme_version = version or "unknown"
    store.theme_installed_at = now
    session.add(store)
    session.commit()

    log.info(
        "[themes] %s: '%s' 설치 version=%s publish=%s",
        store.shop_domain, name, version, body.publish,
    )
    return InstallOut(
        theme_gid=theme["id"],
        theme_name=name,
        published=body.publish,
        version=version or "unknown",
        installed_at=now,
    )
