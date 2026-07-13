"""축① 온보딩 — 브랜드 미리보기 / 주입.

기획안 §1.4: 온보딩은 1회성이다.
이미 주입된 스토어에 다시 주입하려면 force=true 를 명시해야 한다.
머천트가 어드민에서 손댄 값을 말없이 덮어쓰는 것이 이전 접근의 실패 원인이었다.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Session, select

from ..db import get_session
from ..deps import current_user, get_store
from ..engine import fonts
from ..engine.brand import BrandInput, build_payload, build_report
from ..models import OnboardingRun, RunStatus, Store, User
from ..security import decrypt_token
from ..shopify import ShopifyClient, ShopifyError

router = APIRouter(tags=["onboarding"])


class PreviewOut(BaseModel):
    payload: dict
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


@router.post("/preview", response_model=PreviewOut)
def preview(brand: BrandInput, _: User = Depends(current_user)) -> PreviewOut:
    """주입 없이 결과만 계산한다. 스토어 연동이 필요 없으므로 아무 역할이나 호출 가능."""
    return PreviewOut(payload=build_payload(brand), report=build_report(brand))


@router.get("/stores/{store_id}/brand")
async def current_brand(store: Store = Depends(get_store)) -> dict:
    """스토어에 실제로 들어가 있는 값을 읽는다."""
    client = ShopifyClient(store.shop_domain, decrypt_token(store.encrypted_token))
    try:
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

    client = ShopifyClient(store.shop_domain, decrypt_token(store.encrypted_token))
    try:
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
