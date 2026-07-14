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
