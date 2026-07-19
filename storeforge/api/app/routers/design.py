"""헤더·푸터 디자인 프리셋 선택 — 카탈로그 조회 + 라이브 테마 적용.

미리보기는 웹(프런트)이 프리셋 id 별 와이어프레임으로 그린다 — 서버는 어휘(카탈로그)와
적용만 책임진다. 적용은 라이브(MAIN) 테마의 그룹 파일을 themeFilesUpsert 로 바꾼다:
- 헤더: header-group.json 의 header 섹션 settings 만 패치 (아나운스먼트·메뉴 보존)
- 푸터: footer-group.json 재조립 (기존 소셜 링크·소개문은 이어받음)
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ..deps import current_user, get_store
from ..engine.design_presets import (
    FOOTER_PRESETS,
    HEADER_PRESETS,
    build_footer_group,
    build_header_group,
    extract_footer_carryover,
    resolve_schemes,
)
from ..models import Store, User
from ..routers.stores import client_for
from ..shopify import ShopifyClient, ShopifyError

router = APIRouter(prefix="/design", tags=["design"])
log = logging.getLogger(__name__)

_TONES = ("light", "dark", "accent")


class ApplyIn(BaseModel):
    preset_id: str
    tone: str | None = None  # light | dark | accent — 비우면 프리셋 기본 톤


class ApplyOut(BaseModel):
    preset_id: str
    tone: str
    scheme_id: str
    preview_url: str


@router.get("/headers")
async def header_catalog(_: User = Depends(current_user)) -> dict:
    return {"presets": [
        {"id": p["id"], "name": p["name"], "description": p["description"]}
        for p in HEADER_PRESETS
    ]}


@router.get("/footers")
async def footer_catalog(_: User = Depends(current_user)) -> dict:
    return {"presets": [
        {"id": p["id"], "name": p["name"], "description": p["description"], "tone": p["tone"]}
        for p in FOOTER_PRESETS
    ]}


def _guard(store: Store, tone: str | None) -> None:
    if not store.connected:
        raise HTTPException(status.HTTP_409_CONFLICT, "스토어 연결이 확인되지 않았습니다.")
    if store.granted_scopes and "write_themes" not in store.scope_list:
        raise HTTPException(status.HTTP_409_CONFLICT, "write_themes 스코프가 없습니다.")
    if tone is not None and tone not in _TONES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"tone 은 {_TONES} 중 하나여야 합니다.")


async def _theme_ctx(client: ShopifyClient) -> tuple[str, dict[str, str]]:
    """(라이브 테마 gid, 톤→스킴 매핑). 스킴은 스토어의 settings_data 에서 휘도로 고른다."""
    theme_gid = await client.main_theme_gid()
    settings_text = await client.get_theme_file_text(theme_gid, "config/settings_data.json")
    if not settings_text:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "settings_data.json 을 읽지 못했습니다.")
    return theme_gid, resolve_schemes(settings_text)


@router.post("/stores/{store_id}/header", response_model=ApplyOut)
async def apply_header(body: ApplyIn, store: Store = Depends(get_store)) -> ApplyOut:
    _guard(store, body.tone)
    tone = body.tone or "light"
    try:
        client = await client_for(store)
        theme_gid, schemes = await _theme_ctx(client)
        current = await client.get_theme_file_text(theme_gid, "sections/header-group.json")
        if not current:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, "header-group.json 을 읽지 못했습니다.")
        scheme = schemes[tone]
        try:
            new_text = build_header_group(current, body.preset_id, scheme)
        except ValueError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
        await client.theme_files_upsert(theme_gid, "sections/header-group.json", new_text)
    except ShopifyError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    log.info("[design] %s: 헤더 프리셋 %s(%s) 적용", store.shop_domain, body.preset_id, tone)
    return ApplyOut(preset_id=body.preset_id, tone=tone, scheme_id=scheme,
                    preview_url=f"https://{store.shop_domain}")


@router.post("/stores/{store_id}/footer", response_model=ApplyOut)
async def apply_footer(body: ApplyIn, store: Store = Depends(get_store)) -> ApplyOut:
    _guard(store, body.tone)
    preset = next((p for p in FOOTER_PRESETS if p["id"] == body.preset_id), None)
    if preset is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"모르는 푸터 프리셋: {body.preset_id!r}")
    tone = body.tone or preset["tone"]
    try:
        client = await client_for(store)
        theme_gid, schemes = await _theme_ctx(client)
        current = await client.get_theme_file_text(theme_gid, "sections/footer-group.json")
        carry = extract_footer_carryover(current)
        shop_name = store.shop_domain.split(".")[0]
        new_text = build_footer_group(body.preset_id, schemes, carry, shop_name, tone)
        await client.theme_files_upsert(theme_gid, "sections/footer-group.json", new_text)
    except ShopifyError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    log.info("[design] %s: 푸터 프리셋 %s(%s) 적용", store.shop_domain, body.preset_id, tone)
    return ApplyOut(preset_id=body.preset_id, tone=tone, scheme_id=schemes[tone],
                    preview_url=f"https://{store.shop_domain}")
