"""축① 온보딩 — 브랜드 미리보기 / 주입.

기획안 §1.4: 온보딩은 1회성이다.
이미 주입된 스토어에 다시 주입하려면 force=true 를 명시해야 한다.
머천트가 어드민에서 손댄 값을 말없이 덮어쓰는 것이 이전 접근의 실패 원인이었다.
"""

from __future__ import annotations

import base64
import ipaddress
import json
import re
import socket
from collections import Counter
from datetime import datetime, timezone
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlmodel import Session, select

from ..capabilities import missing_scopes_for
from ..config import get_settings
from ..db import get_session
from ..deps import current_user, get_store
from ..engine import fonts, layouts
from ..engine.brand import BrandInput, build_payload, build_report
from ..llm import BrandInterpretationError, interpret, propose
from ..models import OnboardingRun, RunStatus, Store, User
from ..routers.stores import client_for
from ..shopify import ShopifyError

router = APIRouter(tags=["onboarding"])


class PreviewOut(BaseModel):
    payload: dict
    report: dict


class InterpretIn(BaseModel):
    description: str


class InterpretOut(BaseModel):
    brand: BrandInput
    rationale: str
    report: dict


class ApplyIn(BaseModel):
    brand: BrandInput
    force: bool = False


class RunOut(BaseModel):
    id: int
    store_id: int
    status: RunStatus
    error: str | None
    started_at: datetime
    finished_at: datetime | None


@router.get("/fonts")
def list_fonts(_: User = Depends(current_user)) -> list[dict]:
    """LLM 과 관리자 페이지가 고를 수 있는 폰트 화이트리스트 (기획안 §4.3)."""
    return [
        {
            "handle": f.handle,
            "family": f.family,
            "category": f.category,
            "korean": f.korean,
            "weights": sorted({face.weight for face in f.faces}),
        }
        for f in fonts.REGISTRY.values()
    ]


@router.post("/interpret", response_model=InterpretOut)
def interpret_brand(body: InterpretIn, _: User = Depends(current_user)) -> InterpretOut:
    """자연어 브랜드 설명 → 색 4개 + 폰트 4개 (축① LLM 단계).

    LLM 은 여기까지만 한다. 315개 CSS 값은 파생 엔진이 만들고 WCAG 도 코드가 보정한다.
    """
    if not body.description.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "브랜드 설명이 비어 있습니다.")

    key = get_settings().anthropic_api_key or None
    try:
        brand, rationale = interpret(body.description, api_key=key)
    except BrandInterpretationError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

    return InterpretOut(brand=brand, rationale=rationale, report=build_report(brand))


class PaletteOption(BaseModel):
    name: str
    primary: str
    background: str
    foreground: str
    accent: str
    rationale: str


class FontSetOption(BaseModel):
    name: str
    body_font: str
    heading_font: str
    subheading_font: str
    accent_font: str
    rationale: str


class LayoutRec(BaseModel):
    layout_id: str
    rationale: str


class ProposalOut(BaseModel):
    """조합형 선택지 — 컬러셋과 폰트셋은 독립적으로 고른다."""

    palettes: list[PaletteOption]
    font_sets: list[FontSetOption]
    layouts: list[LayoutRec]  # 추천순
    page_width: str


IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}
MAX_IMAGES = 5
MAX_IMAGE_SIDE = 1568  # Claude 비전 권장 상한 — 더 크면 토큰만 늘고 이득이 없다


def _prepare_image(raw: bytes) -> tuple[str, str]:
    """업로드 이미지 → (media_type, base64). 큰 이미지는 줄여서 보낸다."""
    import io

    from PIL import Image

    img = Image.open(io.BytesIO(raw)).convert("RGB")
    if max(img.size) > MAX_IMAGE_SIDE:
        img.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE), Image.LANCZOS)
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=85)
    return "image/jpeg", base64.b64encode(out.getvalue()).decode()


def _site_hints(url: str) -> str | None:
    """참조 사이트에서 색·폰트 힌트를 추출한다.

    사용자가 준 URL 을 서버가 가져가는 것이므로 SSRF 를 막는다: https 만, 호스트의
    모든 해석 주소가 공인 IP 여야 하고, 리다이렉트는 따라가지 않는다.
    실패는 조용히 None — 힌트가 없어도 제안은 돌아간다.
    """
    import httpx

    try:
        parsed = urlparse(url.strip())
        if parsed.scheme != "https" or not parsed.hostname:
            return None
        for info in socket.getaddrinfo(parsed.hostname, 443, proto=socket.IPPROTO_TCP):
            ip = ipaddress.ip_address(info[4][0])
            if not ip.is_global:
                return None

        resp = httpx.get(url, timeout=15, follow_redirects=False,
                         headers={"User-Agent": "StoreForge/1.0 (+brand-hints)"})
        if resp.status_code >= 300:
            return None
        html = resp.text[:500_000]

        colors = Counter(c.lower() for c in re.findall(r"#[0-9a-fA-F]{6}\b", html))
        families = Counter(
            f.strip().strip("'\"")
            for decl in re.findall(r"font-family\s*:\s*([^;}]+)", html)
            for f in decl.split(",")[:1]
        )
        title = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)

        parts = []
        if title:
            parts.append(f"제목: {title.group(1).strip()[:120]}")
        if colors:
            parts.append("자주 쓰인 색: " + ", ".join(c for c, _ in colors.most_common(8)))
        if families:
            parts.append("폰트: " + ", ".join(f for f, _ in families.most_common(5) if f))
        return "\n".join(parts) or None
    except Exception:  # noqa: BLE001 — 힌트는 보조 입력일 뿐, 여기서 죽지 않는다
        return None


@router.get("/layouts")
def list_layouts(_: User = Depends(current_user)) -> list[dict]:
    """홈 레이아웃 프리셋 카탈로그. LLM 제안과 화면 선택지가 같은 목록을 쓴다."""
    return [{"id": l.id, "name": l.name, "description": l.description} for l in layouts.LAYOUTS]


@router.post("/propose", response_model=ProposalOut)
async def propose_brand(
    description: str = Form(""),
    reference_url: str | None = Form(None),
    images: list[UploadFile] = File(default=[]),
    _: User = Depends(current_user),
) -> ProposalOut:
    """설명 + 참고 이미지 + 참조 사이트 → 컬러셋 4 · 폰트셋 3 · 레이아웃 추천.

    선택과 조합은 사람이 한다 — 고른 컬러셋/폰트셋이 브랜드 폼에 채워지고, 수정 후 주입한다.
    """
    if not description.strip() and not images and not (reference_url or "").strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "설명·이미지·참조 URL 중 하나는 필요합니다.")
    if len(images) > MAX_IMAGES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"이미지는 최대 {MAX_IMAGES}장입니다.")

    prepared: list[tuple[str, str]] = []
    for up in images:
        if (up.content_type or "").lower() not in IMAGE_TYPES:
            raise HTTPException(
                status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, f"지원하지 않는 이미지 형식: {up.content_type}"
            )
        raw = await up.read()
        if raw:
            prepared.append(_prepare_image(raw))

    hints = _site_hints(reference_url) if reference_url else None

    key = get_settings().anthropic_api_key or None
    try:
        raw = propose(description, images=prepared, site_hints=hints, api_key=key)
    except BrandInterpretationError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

    return ProposalOut(**raw)


class ChecklistItem(BaseModel):
    key: str
    label: str
    done: bool
    hint: str  # 미완료일 때 다음 행동


class ChecklistOut(BaseModel):
    items: list[ChecklistItem]
    done_count: int
    total: int


@router.get("/stores/{store_id}/checklist", response_model=ChecklistOut)
async def checklist(store: Store = Depends(get_store)) -> ChecklistOut:
    """온보딩 진행률 — 화면 표시가 아니라 **Shopify 실상태**를 읽어 판정한다.

    UAT 교훈: "성공 메시지"와 실제 반영은 다를 수 있다. 그래서 이 체크리스트는 저장된
    플래그가 아니라 매번 스토어에 물어본 결과다.
    """
    items: list[ChecklistItem] = []

    def add(key: str, label: str, done: bool, hint: str) -> None:
        items.append(ChecklistItem(key=key, label=label, done=done, hint=hint))

    add("connect", "스토어 연동", store.connected and not store.missing_scopes,
        "연동 카드에서 자격증명·스코프를 확인하세요")
    add("theme", "테마 설치", bool(store.installed_theme_version),
        "테마 설치 카드에서 설치하세요")

    if not store.connected:
        # 연결이 없으면 나머지는 판정 불가 — 전부 미완료로 보여준다
        for key, label in (("brand", "색·폰트 주입"), ("hero", "히어로 이미지"),
                           ("pages", "페이지"), ("policies", "정책"),
                           ("collections", "컬렉션"), ("menu", "메뉴")):
            add(key, label, False, "먼저 스토어를 연동하세요")
        done = sum(1 for i in items if i.done)
        return ChecklistOut(items=items, done_count=done, total=len(items))

    try:
        client = await client_for(store)

        brand_done = (await client.get_brand_metafield()) is not None
        add("brand", "색·폰트 주입", brand_done, "2단계에서 고르고 4단계에서 주입하세요")

        hero_done = False
        try:
            theme_gid = await client.main_theme_gid()
            raw = await client.get_theme_file_text(theme_gid, "templates/index.json")
            if raw:
                home = json.loads(re.sub(r"/\*.*?\*/", "", raw, flags=re.S))
                hero = next(
                    (home["sections"][s] for s in home["order"]
                     if home["sections"][s]["type"] == "hero"), None)
                img = ((hero or {}).get("settings") or {}).get("image_1") or ""
                hero_done = img.startswith("shopify://")
        except ShopifyError:
            pass
        add("hero", "히어로 이미지", hero_done, "4단계에서 생성·반영하세요")

        try:
            pages = await client.pages_list()
        except ShopifyError:
            pages = []
        handles = " ".join((p.get("handle") or "").lower() for p in pages)
        pages_done = "about" in handles and "contact" in handles
        add("pages", "페이지 (About·Contact 등)", pages_done, "5단계에서 초안 생성 후 반영하세요")

        try:
            policies = await client.shop_policies()
            policies_done = sum(1 for p in policies if (p.get("body") or "").strip()) >= 3
        except ShopifyError:
            policies_done = False
        add("policies", "정책 (약관·환불·배송·프라이버시)", policies_done,
            "관리자에서 정책 자동 관리를 끈 뒤 5단계에서 반영하세요")

        collections = [c for c in await client.collections_list() if c.get("handle") != "frontpage"]
        add("collections", "컬렉션", len(collections) > 0, "5단계 하단에서 생성하세요")

        menus = {m["handle"]: m for m in await client.menus()}
        main_items = (menus.get("main-menu") or {}).get("items") or []
        menu_done = any(i.get("type") == "COLLECTION" for i in main_items)
        add("menu", "메뉴 (헤더·푸터)", menu_done, "6단계에서 제안받아 반영하세요")

    except (ShopifyError, RuntimeError):
        for key, label in (("brand", "색·폰트 주입"), ("hero", "히어로 이미지"),
                           ("pages", "페이지"), ("policies", "정책"),
                           ("collections", "컬렉션"), ("menu", "메뉴")):
            if not any(i.key == key for i in items):
                add(key, label, False, "상태 확인 실패 — 연결 테스트를 다시 해보세요")

    done = sum(1 for i in items if i.done)
    return ChecklistOut(items=items, done_count=done, total=len(items))


class HeroImagesIn(BaseModel):
    description: str = ""
    primary: str
    background: str
    accent: str
    extra: str = ""  # 추가 지시 (예: "모델 없이 제품만", "야외 느낌")


class HeroImagesOut(BaseModel):
    desktop_url: str
    mobile_url: str
    section_id: str


@router.post("/stores/{store_id}/hero-images", response_model=HeroImagesOut)
async def hero_images(body: HeroImagesIn, store: Store = Depends(get_store)) -> HeroImagesOut:
    """AI 히어로 이미지 생성 (PC 16:9 + 모바일 9:16) → Files 업로드 → 홈 히어로에 반영.

    같은 프롬프트를 비율별로 **따로 생성**한다 — 크롭이 아니라서 모바일 구도가 잘리지 않는다.
    테마 hero 섹션의 image_1 / image_1_mobile 에 각각 꽂힌다.
    글자는 이미지에 넣지 않는다 — 헤드라인은 테마 블록의 몫이다.
    """
    from ..engine.images import ImageGenError, generate_hero_pair

    if store.granted_scopes and "write_files" not in store.scope_list:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "write_files 스코프가 없어 이미지를 올릴 수 없습니다 — Dev Dashboard 에서 스코프를 "
            "추가해 새 버전을 Release 하고 앱을 재설치한 뒤 연결 테스트를 다시 하세요.",
        )
    if store.granted_scopes and "write_themes" not in store.scope_list:
        raise HTTPException(status.HTTP_409_CONFLICT, "write_themes 스코프가 없어 홈에 반영할 수 없습니다.")

    try:
        desktop, mobile = generate_hero_pair(
            body.description, body.primary, body.background, body.accent, body.extra
        )
    except ImageGenError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

    try:
        client = await client_for(store)
        theme_gid = await client.main_theme_gid()

        # 홈 템플릿에서 hero 섹션부터 찾는다 — 없는 구성(카탈로그형)이면 이미지 꽂을 곳이 없다.
        raw = await client.get_theme_file_text(theme_gid, "templates/index.json")
        if raw is None:
            raise HTTPException(status.HTTP_409_CONFLICT, "홈 템플릿이 없습니다 — 먼저 테마를 설치하세요.")
        home = json.loads(re.sub(r"/\*.*?\*/", "", raw, flags=re.S))
        hero_sid = next(
            (sid for sid in home["order"] if home["sections"][sid]["type"] == "hero"), None
        )
        if hero_sid is None:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "현재 홈 구성에 히어로 섹션이 없습니다 — 히어로가 있는 구성을 먼저 적용하세요.",
            )

        stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        urls: dict[str, str] = {}
        for kind, data in (("desktop", desktop), ("mobile", mobile)):
            # Gemini 는 보통 JPEG 를 준다 — 매직바이트로 판별한다 (PNG 로 잘못 올리면 CDN 이 거부)
            if data[:8] == b"\x89PNG\r\n\x1a\n":
                mime, ext = "image/png", "png"
            else:
                mime, ext = "image/jpeg", "jpg"
            resource = await client.stage_upload(
                f"storeforge-hero-{store.id}-{stamp}-{kind}.{ext}", mime, data
            )
            gid = await client.file_create_image(resource)
            urls[kind] = await client.file_wait_ready(gid)

        def shop_image_ref(cdn_url: str) -> str:
            # CDN URL 의 파일명이 Files 상의 최종 이름이다 (중복 시 Shopify 가 접미사를 붙인다).
            basename = cdn_url.split("?")[0].rsplit("/", 1)[-1]
            return f"shopify://shop_images/{basename}"

        settings_obj = home["sections"][hero_sid].setdefault("settings", {})
        settings_obj["image_1"] = shop_image_ref(urls["desktop"])
        settings_obj["image_1_mobile"] = shop_image_ref(urls["mobile"])
        # 히어로는 media_type 이 'image' 일 때만 이미지를 렌더한다 — 나누기 원본이 video 모드라
        # 이걸 안 바꾸면 이미지를 넣어도 플레이스홀더가 뜬다 (dasomdev 실증).
        settings_obj["media_type_1"] = "image"
        settings_obj["media_type_1_mobile"] = "image"

        await client.theme_files_upsert(
            theme_gid, "templates/index.json", json.dumps(home, ensure_ascii=False, indent=2)
        )
    except ShopifyError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

    return HeroImagesOut(
        desktop_url=urls["desktop"], mobile_url=urls["mobile"], section_id=hero_sid
    )


def _guard_files_scope(store: Store) -> None:
    if store.granted_scopes and "write_files" not in store.scope_list:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "write_files 스코프가 없어 이미지를 올릴 수 없습니다 — 앱 버전에 스코프를 추가해 "
            "Release 하고 재설치한 뒤 연결 테스트를 다시 하세요.",
        )


async def _upload_image(client, store_id: int, tag: str, data: bytes) -> str:
    """생성 이미지 → Files. 반환: CDN URL. (MIME 은 매직바이트로 판별 — Gemini 는 보통 JPEG)"""
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        mime, ext = "image/png", "png"
    else:
        mime, ext = "image/jpeg", "jpg"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    resource = await client.stage_upload(f"storeforge-{tag}-{store_id}-{stamp}.{ext}", mime, data)
    gid = await client.file_create_image(resource)
    return await client.file_wait_ready(gid)


class StoryImageIn(BaseModel):
    description: str = ""
    primary: str
    background: str
    accent: str
    extra: str = ""


@router.post("/stores/{store_id}/story-image")
async def story_image(body: StoryImageIn, store: Store = Depends(get_store)) -> dict:
    """브랜드 스토리(media-with-content) 섹션 이미지 생성 → 홈에 반영.

    미디어 블록도 히어로처럼 media_type 이 'image' 여야 렌더된다 — 같은 함정, 같은 처방.
    """
    from ..engine.images import ImageGenError, build_story_prompt, generate_one

    _guard_files_scope(store)
    if store.granted_scopes and "write_themes" not in store.scope_list:
        raise HTTPException(status.HTTP_409_CONFLICT, "write_themes 스코프가 없어 홈에 반영할 수 없습니다.")

    try:
        data = generate_one(
            build_story_prompt(body.description, body.primary, body.background, body.accent, body.extra),
            "4:5",
        )
    except ImageGenError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

    try:
        client = await client_for(store)
        theme_gid = await client.main_theme_gid()
        raw = await client.get_theme_file_text(theme_gid, "templates/index.json")
        if raw is None:
            raise HTTPException(status.HTTP_409_CONFLICT, "홈 템플릿이 없습니다 — 먼저 테마를 설치하세요.")
        home = json.loads(re.sub(r"/\*.*?\*/", "", raw, flags=re.S))

        # media-with-content 섹션 → 그 안의 media 블록(_media 계열)을 찾는다
        target_block = None
        for sid in home["order"]:
            sec = home["sections"][sid]
            if sec["type"] != "media-with-content":
                continue
            for block in (sec.get("blocks") or {}).values():
                if "_media" in (block.get("type") or ""):
                    target_block = block
                    break
            if target_block:
                break
        if target_block is None:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "현재 홈 구성에 브랜드 스토리(미디어+텍스트) 섹션이 없습니다 — "
                "'쇼핑몰 표준' 또는 '슬라이드 커머스' 구성을 먼저 적용하세요.",
            )

        url = await _upload_image(client, store.id, "story", data)
        basename = url.split("?")[0].rsplit("/", 1)[-1]
        settings_obj = target_block.setdefault("settings", {})
        settings_obj["image"] = f"shopify://shop_images/{basename}"
        settings_obj["media_type"] = "image"

        await client.theme_files_upsert(
            theme_gid, "templates/index.json", json.dumps(home, ensure_ascii=False, indent=2)
        )
    except ShopifyError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

    return {"image_url": url}


class CollectionImagesIn(BaseModel):
    description: str = ""
    primary: str
    accent: str
    limit: int = 6


@router.post("/stores/{store_id}/collection-images")
async def collection_images(body: CollectionImagesIn, store: Store = Depends(get_store)) -> dict:
    """컬렉션마다 배너 이미지를 생성해 대표 이미지로 건다 (1:1, 컬렉션당 1장).

    컬렉션 페이지·카테고리 카드가 이 이미지를 쓴다. 이미 이미지가 있는 컬렉션은 건너뛴다 —
    사람이 고른 이미지를 말없이 덮지 않는다.
    """
    from ..engine.images import ImageGenError, build_collection_prompt, generate_one

    _guard_files_scope(store)

    try:
        client = await client_for(store)
        data = await client.graphql(
            "{ collections(first: 20) { nodes { id handle title image { url } } } }"
        )
        targets = [
            c for c in data["collections"]["nodes"]
            if c["handle"] != "frontpage" and not c.get("image")
        ][: max(1, min(body.limit, 10))]
    except ShopifyError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

    if not targets:
        return {"results": [], "note": "이미지가 없는 컬렉션이 없습니다 — 전부 채워져 있습니다."}

    results = []
    for col in targets:
        try:
            img = generate_one(
                build_collection_prompt(col["title"], body.description, body.primary, body.accent),
                "1:1",
            )
            url = await _upload_image(client, store.id, f"col-{col['handle']}", img)
            await client.collection_update_image(col["id"], url, alt=col["title"])
            results.append({"title": col["title"], "handle": col["handle"], "ok": True, "url": url})
        except (ImageGenError, ShopifyError) as exc:
            # 한 컬렉션이 실패해도 나머지는 계속 — 어디까지 됐는지 결과에 남긴다
            results.append({"title": col["title"], "handle": col["handle"], "ok": False, "error": str(exc)[:200]})

    return {"results": results}


class LayoutIn(BaseModel):
    layout_id: str


@router.post("/stores/{store_id}/layout")
async def apply_layout(body: LayoutIn, store: Store = Depends(get_store)) -> dict:
    """선택한 홈 레이아웃을 스토어의 라이브 테마에 반영한다 (templates/index.json 업서트).

    색·폰트는 건드리지 않는다 — 그건 metafield 주입의 몫이다.
    """
    if body.layout_id not in layouts.LAYOUTS_BY_ID:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"모르는 레이아웃: {body.layout_id}")
    if store.granted_scopes and "write_themes" not in store.scope_list:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "write_themes 스코프가 없어 레이아웃을 반영할 수 없습니다."
        )

    version = store.installed_theme_version
    if version in (None, "unknown"):
        version = None  # latest 기준으로 만든다

    try:
        home = layouts.build_home(body.layout_id, version)
    except Exception as exc:  # noqa: BLE001 — zip 다운로드 실패 등
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"레이아웃 빌드 실패: {exc}") from exc

    try:
        client = await client_for(store)
        theme_gid = await client.main_theme_gid()
        await client.theme_files_upsert(
            theme_gid, "templates/index.json", json.dumps(home, ensure_ascii=False, indent=2)
        )
    except ShopifyError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

    return {"applied": body.layout_id, "sections": home["order"]}


@router.post("/preview", response_model=PreviewOut)
def preview(brand: BrandInput, _: User = Depends(current_user)) -> PreviewOut:
    """주입 없이 결과만 계산한다. 스토어 연동이 필요 없으므로 아무 역할이나 호출 가능."""
    return PreviewOut(payload=build_payload(brand), report=build_report(brand))


@router.get("/stores/{store_id}/brand")
async def current_brand(store: Store = Depends(get_store)) -> dict:
    """스토어에 실제로 들어가 있는 값을 읽는다."""
    try:
        client = await client_for(store)
        existing = await client.get_brand_metafield()
    except (ShopifyError, RuntimeError) as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    return {"applied": existing is not None, "metafield": existing}


@router.post("/stores/{store_id}/apply", response_model=RunOut)
async def apply_brand(
    body: ApplyIn,
    store: Store = Depends(get_store),
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> RunOut:
    if not store.connected:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "스토어 연결이 확인되지 않았습니다. 먼저 연결 테스트를 통과시키세요.",
        )

    # 축①(브랜드 주입)이 켜져 있어야 한다. 스코프는 요구하지 않지만, 이 스토어에서 무엇을 켰는지는
    # 명시적으로 관리한다 (통합 앱이므로 스토어마다 쓰는 모듈이 다르다).
    if "storeforge" not in store.module_list:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "이 스토어에서 StoreForge 모듈이 꺼져 있습니다. 스토어 설정에서 켠 뒤 다시 시도하세요.",
        )

    # 켠 모듈이 요구하는 스코프가 없으면 어차피 Shopify 가 403 을 준다. 그 전에 이유를 분명히 말해준다.
    # (축① 자체는 샵 메타필드만 쓰므로 요구 스코프가 없다 — 여기서 막히는 일은 없어야 정상이다.)
    if missing_scopes_for(["storeforge"], store.scope_list):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Shopify 앱에 필수 스코프가 없습니다: "
            + ", ".join(missing_scopes_for(["storeforge"], store.scope_list))
            + " — Dev Dashboard 에서 스코프를 추가해 새 버전을 Release 하고 앱을 재설치한 뒤 "
            "연결 테스트를 다시 하세요.",
        )

    payload = build_payload(body.brand)
    report = build_report(body.brand)

    # 엔진이 보정을 마친 뒤에도 WCAG 를 못 맞추면 그건 엔진 버그다. 주입하지 않는다.
    if not report["wcag_pass"]:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "생성된 팔레트가 WCAG 검증을 통과하지 못했습니다. 주입을 중단합니다.",
        )

    run = OnboardingRun(
        store_id=store.id,
        started_by_id=user.id,
        status=RunStatus.running,
        brand_input_json=body.brand.model_dump_json(),
        payload_json=json.dumps(payload, ensure_ascii=False),
        report_json=json.dumps(report, ensure_ascii=False),
    )
    session.add(run)
    session.commit()
    session.refresh(run)

    try:
        client = await client_for(store)

        if not body.force:
            existing = await client.get_brand_metafield()
            if existing is not None:
                raise ShopifyError(
                    "이미 온보딩이 적용된 스토어입니다. 머천트가 수동 수정했을 수 있으므로 "
                    "덮어쓰려면 force 를 명시하세요. (기획안 §1.4 — 온보딩은 1회성)"
                )

        await client.set_brand_metafield(payload)
        run.status = RunStatus.succeeded

    except (ShopifyError, RuntimeError) as exc:
        run.status = RunStatus.failed
        run.error = str(exc)

    run.finished_at = datetime.now(timezone.utc)
    session.add(run)
    session.commit()
    session.refresh(run)

    if run.status == RunStatus.failed:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, run.error or "주입 실패")

    return RunOut(**run.model_dump())


@router.get("/stores/{store_id}/runs", response_model=list[RunOut])
def list_runs(
    store: Store = Depends(get_store), session: Session = Depends(get_session)
) -> list[RunOut]:
    rows = session.exec(
        select(OnboardingRun)
        .where(OnboardingRun.store_id == store.id)
        .order_by(OnboardingRun.id.desc())  # type: ignore[attr-defined]
    ).all()
    return [RunOut(**r.model_dump()) for r in rows]
