"""ListPilot (축②) — 상품 원본 데이터 → AI 초안 → 사람 검수 → Shopify 등록.

`dasomweb/DW-ListPilot` 이식. 흐름은 원본과 같다:

    파일 업로드(이미지/PDF/엑셀/CSV) → 추출 → 초안(Listing) → 편집 → 등록

원본과 달라진 것은 `engine/listpilot/__init__.py` 주석에 정리했다. 요지는 셋이다:
DB 는 통합 앱의 SQLModel 을 쓰고, 등록은 REST 가 아니라 `productSet`, 이미지는 R2 가 아니라
Shopify staged upload.

**추출은 자동, 등록은 수동이다.** AI 가 뽑은 걸 곧바로 스토어에 밀어 넣지 않는다 —
잘못 뽑힌 상품이 라이브 스토어에 뜨는 것보다, 사람이 한 번 보고 누르는 편이 낫다.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlmodel import Session, select

from ..capabilities import missing_scopes_for
from ..db import get_session
from ..deps import current_user, get_store
from ..engine.listpilot import gemini, parsers, tags as tag_engine
from ..engine.listpilot.presets import DEFAULT_INDUSTRY, INDUSTRIES
from ..models import Listing, ListingImage, ListingStatus, Store, User
from ..routers.stores import client_for
from ..shopify import ShopifyError

router = APIRouter(prefix="/listpilot", tags=["listpilot"])
log = logging.getLogger(__name__)

MODULE_ID = "listpilot"

IMAGE_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp"}
SHEET_TYPES = {
    "text/csv",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


class VariantIn(BaseModel):
    option_name: str = "Title"
    option_value: str = "Default Title"
    price: float | None = None
    sku: str | None = None
    barcode: str | None = None
    quantity: int = 0
    weight_kg: float | None = None


class ListingOut(BaseModel):
    id: int
    store_id: int
    title: str
    body_html: str
    vendor: str | None
    product_type: str | None
    tags: list[str]
    confidence: float | None
    status: ListingStatus
    shopify_product_gid: str | None
    error: str | None
    variants: list[VariantIn]
    image_count: int
    created_at: datetime
    pushed_at: datetime | None


class ListingPatch(BaseModel):
    title: str | None = None
    body_html: str | None = None
    vendor: str | None = None
    product_type: str | None = None
    tags: list[str] | None = None
    variants: list[VariantIn] | None = None


def _out(listing: Listing, image_count: int) -> ListingOut:
    return ListingOut(
        id=listing.id,
        store_id=listing.store_id,
        title=listing.title,
        body_html=listing.body_html,
        vendor=listing.vendor,
        product_type=listing.product_type,
        tags=[t for t in listing.tags.split(",") if t],
        confidence=listing.confidence,
        status=listing.status,
        shopify_product_gid=listing.shopify_product_gid,
        error=listing.error,
        variants=[VariantIn(**v) for v in json.loads(listing.variants_json)],
        image_count=image_count,
        created_at=listing.created_at,
        pushed_at=listing.pushed_at,
    )


def _guard(store: Store) -> None:
    if MODULE_ID not in store.module_list:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "이 스토어에서 ListPilot 모듈이 꺼져 있습니다. 스토어 설정에서 켠 뒤 다시 시도하세요.",
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


def _get_listing(session: Session, store: Store, listing_id: int) -> Listing:
    listing = session.get(Listing, listing_id)
    # 다른 스토어의 초안이면 '없다'고 답한다 — 존재 여부조차 알려주지 않는다 (stores.py 와 같은 원칙).
    if not listing or listing.store_id != store.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "초안을 찾을 수 없습니다.")
    return listing


def _image_counts(session: Session, listing_ids: list[int]) -> dict[int, int]:
    if not listing_ids:
        return {}
    rows = session.exec(
        select(ListingImage.listing_id).where(ListingImage.listing_id.in_(listing_ids))
    ).all()
    counts: dict[int, int] = {}
    for lid in rows:
        counts[lid] = counts.get(lid, 0) + 1
    return counts


def _variants_from_extracted(extracted: dict) -> list[dict]:
    """추출 결과의 options → 변형 목록.

    옵션이 없으면 Shopify 관례대로 단일 'Default Title' 변형 하나를 만든다.
    옵션이 여럿이면 첫 축만 쓴다 — 조합 폭발(색×사이즈×소재)을 자동으로 만들어 두면
    사람이 지우는 게 더 일이다. 필요하면 화면에서 추가한다.
    """
    price = extracted.get("price")
    sku = extracted.get("sku")
    barcode = extracted.get("barcode")
    qty = int(extracted.get("quantity") or 0)
    weight = extracted.get("weight_kg")

    options = extracted.get("options") or []
    first = next((o for o in options if o.get("values")), None)

    if not first:
        return [
            VariantIn(
                price=price, sku=sku, barcode=barcode, quantity=qty, weight_kg=weight
            ).model_dump()
        ]

    return [
        VariantIn(
            option_name=first.get("name") or "Title",
            option_value=str(v),
            price=price,
            sku=sku,
            barcode=barcode,
            quantity=qty,
            weight_kg=weight,
        ).model_dump()
        for v in first["values"]
    ]


def _listing_from_extracted(
    extracted: dict, store: Store, user: User, industry: str
) -> Listing:
    generated = tag_engine.generate_tags(extracted, industry)
    return Listing(
        store_id=store.id,
        created_by_id=user.id,
        title=str(extracted.get("title") or "Untitled Product"),
        body_html=str(extracted.get("description") or ""),
        vendor=extracted.get("vendor"),
        product_type=extracted.get("product_type"),
        tags=",".join(generated),
        confidence=extracted.get("confidence"),
        variants_json=json.dumps(_variants_from_extracted(extracted), ensure_ascii=False),
    )


@router.get("/industries")
def list_industries(_: User = Depends(current_user)) -> dict:
    """업종 프리셋. 추출 결과를 어떤 태그 축으로 정규화할지 정한다."""
    return {"industries": list(INDUSTRIES), "default": DEFAULT_INDUSTRY}


@router.post("/stores/{store_id}/extract", response_model=list[ListingOut], status_code=201)
async def extract(
    file: UploadFile = File(...),
    industry: str = DEFAULT_INDUSTRY,
    store: Store = Depends(get_store),
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> list[ListingOut]:
    """파일 하나 → 상품 초안 여러 개.

    이미지·PDF 는 Gemini 비전으로 읽고(인보이스면 한 장에서 여러 상품이 나온다),
    엑셀·CSV 는 표를 그대로 읽는다. 등록은 하지 않는다.
    """
    _guard(store)

    raw = await file.read()
    if not raw:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "빈 파일입니다.")

    content_type = (file.content_type or "").lower()
    filename = (file.filename or "").lower()

    listings: list[Listing] = []
    image_bytes: bytes | None = None

    try:
        if content_type in IMAGE_TYPES:
            image_bytes = parsers.process_image(raw)
            for ex in gemini.extract_from_image(image_bytes, "image/webp"):
                listings.append(_listing_from_extracted(ex, store, user, industry))

        elif content_type == "application/pdf" or filename.endswith(".pdf"):
            for page in parsers.pdf_page_images(raw):
                for ex in gemini.extract_from_image(page, "image/png"):
                    listings.append(_listing_from_extracted(ex, store, user, industry))

        elif content_type in SHEET_TYPES or filename.endswith((".csv", ".xlsx", ".xls")):
            rows = (
                parsers.parse_csv(raw)
                if filename.endswith(".csv") or content_type == "text/csv"
                else parsers.parse_excel(raw)
            )
            if not rows:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "표에서 읽을 행이 없습니다.")
            mapping = parsers.auto_map_columns(list(rows[0].keys()))
            if "title" not in mapping:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    "상품명 컬럼을 찾지 못했습니다. 헤더에 title/product name/item 중 하나가 필요합니다.",
                )
            for row in rows:
                ex = parsers.row_to_extracted(row, mapping)
                listings.append(_listing_from_extracted(ex, store, user, industry))

        else:
            raise HTTPException(
                status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                f"지원하지 않는 형식입니다: {content_type or filename}",
            )

    except gemini.GeminiNotConfigured as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc

    if not listings:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "상품을 하나도 추출하지 못했습니다.")

    for listing in listings:
        session.add(listing)
    session.commit()

    # 상품 사진을 올린 경우, 그 사진이 곧 상품 이미지다. 초안이 하나일 때만 붙인다 —
    # 인보이스 한 장에서 상품 5개가 나왔다면 그 스캔 이미지는 어느 상품의 사진도 아니다.
    if image_bytes and len(listings) == 1:
        session.refresh(listings[0])
        session.add(
            ListingImage(
                listing_id=listings[0].id,
                data=image_bytes,
                alt=listings[0].title,
                content_type="image/webp",
            )
        )
        session.commit()

    for listing in listings:
        session.refresh(listing)

    counts = _image_counts(session, [x.id for x in listings])
    return [_out(x, counts.get(x.id, 0)) for x in listings]


@router.get("/stores/{store_id}/listings", response_model=list[ListingOut])
def list_listings(
    store: Store = Depends(get_store), session: Session = Depends(get_session)
) -> list[ListingOut]:
    rows = session.exec(
        select(Listing).where(Listing.store_id == store.id).order_by(Listing.id.desc())
    ).all()
    counts = _image_counts(session, [r.id for r in rows])
    return [_out(r, counts.get(r.id, 0)) for r in rows]


@router.patch("/stores/{store_id}/listings/{listing_id}", response_model=ListingOut)
def update_listing(
    listing_id: int,
    body: ListingPatch,
    store: Store = Depends(get_store),
    session: Session = Depends(get_session),
) -> ListingOut:
    listing = _get_listing(session, store, listing_id)

    data = body.model_dump(exclude_unset=True)
    if "tags" in data:
        listing.tags = ",".join(data.pop("tags") or [])
    if "variants" in data:
        listing.variants_json = json.dumps(
            [v for v in data.pop("variants")], ensure_ascii=False, default=str
        )
    for field, value in data.items():
        setattr(listing, field, value)

    listing.updated_at = datetime.now(timezone.utc)
    session.add(listing)
    session.commit()
    session.refresh(listing)
    return _out(listing, _image_counts(session, [listing.id]).get(listing.id, 0))


@router.post("/stores/{store_id}/listings/{listing_id}/describe", response_model=ListingOut)
def describe(
    listing_id: int,
    store: Store = Depends(get_store),
    session: Session = Depends(get_session),
) -> ListingOut:
    """상세설명을 AI 로 다시 쓴다. 실패해도 기존 설명은 남는다."""
    _guard(store)
    listing = _get_listing(session, store, listing_id)

    listing.body_html = gemini.generate_description(
        title=listing.title,
        vendor=listing.vendor,
        product_type=listing.product_type,
        tags=[t for t in listing.tags.split(",") if t],
        fallback=listing.body_html,
    )
    listing.updated_at = datetime.now(timezone.utc)
    session.add(listing)
    session.commit()
    session.refresh(listing)
    return _out(listing, _image_counts(session, [listing.id]).get(listing.id, 0))


@router.delete("/stores/{store_id}/listings/{listing_id}", status_code=204, response_model=None)
def delete_listing(
    listing_id: int,
    store: Store = Depends(get_store),
    session: Session = Depends(get_session),
) -> None:
    """초안만 지운다. 이미 등록된 Shopify 상품은 건드리지 않는다 —
    여기서 지우면 라이브 스토어의 상품이 사라진다."""
    listing = _get_listing(session, store, listing_id)
    for img in session.exec(
        select(ListingImage).where(ListingImage.listing_id == listing.id)
    ).all():
        session.delete(img)
    session.delete(listing)
    session.commit()


@router.post("/stores/{store_id}/listings/{listing_id}/push", response_model=ListingOut)
async def push(
    listing_id: int,
    store: Store = Depends(get_store),
    session: Session = Depends(get_session),
) -> ListingOut:
    """초안을 Shopify 에 등록한다. **draft 상태로 올린다** — 검수 없이 바로 팔리게 두지 않는다."""
    _guard(store)
    listing = _get_listing(session, store, listing_id)

    variants = [VariantIn(**v) for v in json.loads(listing.variants_json)]
    if not variants:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "변형이 하나도 없습니다.")

    images = session.exec(
        select(ListingImage)
        .where(ListingImage.listing_id == listing.id)
        .order_by(ListingImage.position)
    ).all()

    try:
        client = await client_for(store)
        location = await client.primary_location_gid()

        files = []
        for i, img in enumerate(images):
            resource_url = await client.stage_upload(
                f"listing-{listing.id}-{i}.webp", img.content_type, img.data
            )
            files.append(
                {
                    "originalSource": resource_url,
                    "contentType": "IMAGE",
                    "alt": img.alt or listing.title,
                }
            )

        option_name = variants[0].option_name or "Title"
        product_input: dict = {
            "title": listing.title,
            "descriptionHtml": listing.body_html,
            "status": "DRAFT",
            "tags": [t for t in listing.tags.split(",") if t],
            "productOptions": [
                {
                    "name": option_name,
                    "values": [{"name": v.option_value or "Default Title"} for v in variants],
                }
            ],
            "variants": [_variant_input(v, option_name, location) for v in variants],
        }
        if listing.vendor:
            product_input["vendor"] = listing.vendor
        if listing.product_type:
            product_input["productType"] = listing.product_type
        if files:
            product_input["files"] = files
        if listing.shopify_product_gid:
            product_input["id"] = listing.shopify_product_gid  # 재등록이면 갱신한다

        gid = await client.product_set(product_input)

    except ShopifyError as exc:
        listing.status = ListingStatus.failed
        listing.error = str(exc)
        session.add(listing)
        session.commit()
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

    listing.status = ListingStatus.pushed
    listing.shopify_product_gid = gid
    listing.error = None
    listing.pushed_at = datetime.now(timezone.utc)
    session.add(listing)
    session.commit()
    session.refresh(listing)

    log.info("[listpilot] %s: %s 등록됨 (%s)", store.shop_domain, listing.title, gid)
    return _out(listing, len(images))


def _variant_input(v: VariantIn, option_name: str, location: str | None) -> dict:
    out: dict = {
        "optionValues": [
            {"optionName": option_name, "name": v.option_value or "Default Title"}
        ],
        "price": str(v.price if v.price is not None else 0),
    }
    if v.sku:
        out["sku"] = v.sku
    if v.barcode:
        out["barcode"] = v.barcode
    if v.weight_kg:
        out["inventoryItem"] = {
            "measurement": {"weight": {"value": v.weight_kg, "unit": "KILOGRAMS"}}
        }
    # 로케이션을 모르면 재고를 넣을 수 없다. 상품 자체는 등록된다.
    if location and v.quantity:
        out["inventoryQuantities"] = [
            {"locationId": location, "name": "available", "quantity": v.quantity}
        ]
    return out
