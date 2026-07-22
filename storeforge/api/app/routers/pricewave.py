"""Pricewave — 할인 코드 시각화 (dasomweb/pricewave 이식).

Shopify 의 active 할인 코드를 읽어 가장 큰 것 하나를 `shop.metafields.pricewave.active_discount`
에 넣는다. 테마 블록(`blocks/pricewave-sale-price.liquid`)이 그 값을 읽어 상품 페이지에
"원가 / 쿠폰 사용 시 가격"을 그린다. **가격은 절대 쓰지 않는다.**

원본은 Remix 앱이 자기 세션으로 스토어를 돌았지만, 여기서는 통합 앱의 스토어별 자격증명을 쓴다.
Pricewave 모듈을 켠 스토어만 동기화 대상이다.

metafield 정의(metafieldDefinitionCreate)는 만들지 않는다. Liquid 는 정의나 storefront access
설정과 무관하게 메타필드를 읽으므로 필요 없고, 만들지 않으면 실패할 것도 없다.
(Storefront API 로 읽어야 할 일이 생기면 그때 정의를 추가한다.)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Session, select

from ..capabilities import missing_scopes_for
from ..db import get_session
from ..deps import get_store
from ..engine.pricewave import KEY, NAMESPACE, ActiveDiscount, parse_discounts, pick_best
from ..models import Store
from ..routers.stores import client_for
from ..shopify import ShopifyError

router = APIRouter(prefix="/pricewave", tags=["pricewave"])
log = logging.getLogger(__name__)

MODULE_ID = "pricewave"


class DiscountOut(BaseModel):
    id: str
    code: str
    type: str
    value: float
    title: str
    starts_at: str
    ends_at: str | None


class SyncOut(BaseModel):
    active: list[DiscountOut]  # 지금 살아 있는 코드 할인 전부
    picked: DiscountOut | None  # 그중 실제로 손님에게 보여줄 것 (가장 큰 할인)
    synced_at: datetime


def _out(d: ActiveDiscount) -> DiscountOut:
    return DiscountOut(
        id=d.id,
        code=d.code,
        type=d.type,
        value=d.value,
        title=d.title,
        starts_at=d.starts_at,
        ends_at=d.ends_at,
    )


async def sync_store(store: Store) -> tuple[list[ActiveDiscount], ActiveDiscount | None]:
    """스토어 하나를 동기화한다. 스케줄러와 라우터가 함께 쓴다.

    살아 있는 할인이 없으면 메타필드를 **지운다** — 남겨두면 끝난 세일 가격이 계속 걸린다.
    """
    client = await client_for(store)
    active = parse_discounts(await client.active_discounts())
    picked = pick_best(active)

    if picked:
        await client.set_shop_metafield(NAMESPACE, KEY, picked.to_metafield())
    else:
        await client.delete_shop_metafield(NAMESPACE, KEY)

    return active, picked


def _guard(store: Store) -> None:
    if MODULE_ID not in store.module_list:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "이 스토어에서 Pricewave 모듈이 꺼져 있습니다. 스토어 설정에서 켠 뒤 다시 시도하세요.",
        )
    missing = missing_scopes_for([MODULE_ID], store.scope_list)
    if missing:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Shopify 앱에 필수 스코프가 없습니다: "
            + ", ".join(missing)
            + " — Dev Dashboard 에서 스코프를 추가해 새 버전을 Release 하고 앱을 재설치한 뒤 "
            "연결 테스트를 다시 하세요.",
        )


@router.post("/stores/{store_id}/sync", response_model=SyncOut)
async def sync(store: Store = Depends(get_store)) -> SyncOut:
    """지금 즉시 동기화. 스케줄러를 기다리지 않고 결과를 보고 싶을 때 쓴다."""
    _guard(store)
    try:
        active, picked = await sync_store(store)
    except ShopifyError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

    return SyncOut(
        active=[_out(d) for d in active],
        picked=_out(picked) if picked else None,
        synced_at=datetime.now(timezone.utc),
    )


@router.get("/stores/{store_id}", response_model=SyncOut | None)
async def current(store: Store = Depends(get_store)) -> SyncOut | None:
    """지금 스토어에 걸려 있는 값. 동기화하지 않고 읽기만 한다."""
    _guard(store)
    try:
        client = await client_for(store)
        mf = await client.get_shop_metafield(NAMESPACE, KEY)
    except ShopifyError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

    if not mf:
        return None

    v = mf["value"]
    picked = DiscountOut(
        id=v["id"],
        code=v["code"],
        type=v["type"],
        value=v["value"],
        title=v["title"],
        starts_at=v["startsAt"],
        ends_at=v.get("endsAt"),
    )
    return SyncOut(active=[picked], picked=picked, synced_at=mf["updated_at"])


async def sync_all(session: Session) -> None:
    """스케줄러가 부른다. 한 스토어가 실패해도 나머지는 계속 돈다."""
    stores = session.exec(select(Store).where(Store.connected == True)).all()  # noqa: E712
    targets = [s for s in stores if MODULE_ID in s.module_list]

    for store in targets:
        if missing_scopes_for([MODULE_ID], store.scope_list):
            continue  # 스코프가 없으면 어차피 실패한다. 화면이 이미 이유를 보여주고 있다.
        try:
            active, picked = await sync_store(store)
            log.info(
                "[pricewave] %s: active=%d picked=%s",
                store.shop_domain,
                len(active),
                picked.code if picked else "none",
            )
        except (ShopifyError, RuntimeError) as exc:
            log.warning("[pricewave] %s 동기화 실패: %s", store.shop_domain, exc)
