"""페이지 · 정책 · 컬렉션 생성 — 온보딩 5단계.

- 페이지(About/Contact/FAQ/배송안내): AI 초안 → **사람 검토** → pageCreate (발행 여부 선택)
- 정책(약관·환불·배송·프라이버시): AI 초안 → 검토 → shopPolicyUpdate
  정책은 초안 상태가 없어 쓰는 순간 라이브다. 그래서 반영 요청에 confirm 플래그를
  강제한다 — AI 초안을 법적 검토 없이 라이브에 걸면 안 된다.
- 컬렉션(카테고리): 스마트 컬렉션으로 만든다. ListPilot 이 등록하는 상품이 태그만 맞으면
  자동으로 들어간다. 컬렉션·상품 페이지 자체는 테마 템플릿이 렌더하므로 여기서 만들 것은
  데이터뿐이다.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ..config import get_settings
from ..deps import current_user, get_store
from ..llm import PAGE_KINDS, POLICY_TYPES, BrandInterpretationError, generate_pages
from ..models import Store, User
from ..routers.stores import client_for
from ..shopify import ShopifyError

router = APIRouter(prefix="/pages", tags=["pages"])
log = logging.getLogger(__name__)

# 페이지 종류 → 테마 템플릿. contact 는 문의 폼이 있는 page.contact 를 쓴다.
TEMPLATE_BY_KIND = {"contact": "contact", "about": "info", "faq": "info", "shipping-info": "info"}


class DraftIn(BaseModel):
    description: str
    page_kinds: list[str] = list(PAGE_KINDS)
    policy_types: list[str] = list(POLICY_TYPES)


class PageDraft(BaseModel):
    kind: str
    title: str
    body_html: str


class PolicyDraft(BaseModel):
    type: str
    body_html: str


class DraftOut(BaseModel):
    pages: list[PageDraft]
    policies: list[PolicyDraft]


class ApplyPagesIn(BaseModel):
    pages: list[PageDraft] = []
    publish: bool = True

    policies: list[PolicyDraft] = []
    # 정책은 쓰는 순간 라이브라서, 검토했다는 명시적 확인 없이는 반영하지 않는다.
    policies_reviewed: bool = False


class AppliedPage(BaseModel):
    kind: str
    title: str
    handle: str
    published: bool


class ApplyPagesOut(BaseModel):
    pages: list[AppliedPage]
    policies: list[str]  # 반영된 정책 타입


class CollectionsIn(BaseModel):
    # [{title: "Tops", tag: "category:tops"}] — tag 를 주면 스마트 컬렉션
    collections: list[dict]


@router.get("/catalog")
def catalog(_: User = Depends(current_user)) -> dict:
    """화면이 체크박스 목록을 그릴 때 쓰는 페이지·정책 종류."""
    return {"page_kinds": PAGE_KINDS, "policy_types": POLICY_TYPES}


@router.post("/stores/{store_id}/draft", response_model=DraftOut)
async def draft(
    body: DraftIn, store: Store = Depends(get_store), _: User = Depends(current_user)
) -> DraftOut:
    """AI 초안 생성 — 아무것도 쓰지 않는다. 검토·수정 후 apply 로 반영한다."""
    if not body.description.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "브랜드 설명이 비어 있습니다.")
    bad = [k for k in body.page_kinds if k not in PAGE_KINDS] + [
        t for t in body.policy_types if t not in POLICY_TYPES
    ]
    if bad:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"모르는 종류: {', '.join(bad)}")

    try:
        raw = generate_pages(
            body.description,
            body.page_kinds,
            body.policy_types,
            api_key=get_settings().anthropic_api_key or None,
        )
    except BrandInterpretationError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

    return DraftOut(
        pages=[PageDraft(**p) for p in raw["pages"]],
        policies=[PolicyDraft(**p) for p in raw["policies"]],
    )


@router.post("/stores/{store_id}/apply", response_model=ApplyPagesOut)
async def apply(body: ApplyPagesIn, store: Store = Depends(get_store)) -> ApplyPagesOut:
    """검토를 마친 초안을 실제로 반영한다."""
    if not store.connected:
        raise HTTPException(status.HTTP_409_CONFLICT, "스토어 연결이 확인되지 않았습니다.")
    if body.pages and store.granted_scopes and "write_content" not in store.scope_list:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "write_content 스코프가 없어 페이지를 만들 수 없습니다 — 앱 버전에 스코프를 추가해 "
            "Release 하고 재설치한 뒤 연결 테스트를 다시 하세요.",
        )
    if body.policies:
        if not body.policies_reviewed:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "정책 문서는 반영 즉시 라이브가 됩니다 — 검토 확인(policies_reviewed)이 필요합니다.",
            )
        if store.granted_scopes and "write_legal_policies" not in store.scope_list:
            raise HTTPException(
                status.HTTP_409_CONFLICT, "write_legal_policies 스코프가 없어 정책을 쓸 수 없습니다."
            )

    client = await client_for(store)
    applied_pages: list[AppliedPage] = []
    applied_policies: list[str] = []

    try:
        for page in body.pages:
            created = await client.page_create(
                page.title,
                page.body_html,
                publish=body.publish,
                template_suffix=TEMPLATE_BY_KIND.get(page.kind),
            )
            applied_pages.append(
                AppliedPage(
                    kind=page.kind,
                    title=created["title"],
                    handle=created["handle"],
                    published=body.publish,
                )
            )
        for policy in body.policies:
            if policy.type not in POLICY_TYPES:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, f"모르는 정책 타입: {policy.type}")
            await client.shop_policy_update(policy.type, policy.body_html)
            applied_policies.append(policy.type)
    except ShopifyError as exc:
        # 일부만 반영된 상태로 죽을 수 있다 — 무엇까지 됐는지 함께 알려준다.
        done = ", ".join([p.handle for p in applied_pages] + applied_policies) or "없음"
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"{exc} (여기까지는 반영됨: {done})"
        ) from exc

    log.info(
        "[pages] %s: 페이지 %d개, 정책 %d개 반영",
        store.shop_domain, len(applied_pages), len(applied_policies),
    )
    return ApplyPagesOut(pages=applied_pages, policies=applied_policies)


@router.post("/stores/{store_id}/collections")
async def create_collections(body: CollectionsIn, store: Store = Depends(get_store)) -> dict:
    """카테고리(컬렉션) 생성. 컬렉션 페이지는 테마 템플릿이 자동으로 렌더한다.

    tag 를 준 항목은 스마트 컬렉션 — ListPilot 태그(`category:tops` 형식)와 맞물린다.
    write_products 는 ListPilot 모듈이 이미 요구하는 스코프라 대개 부여돼 있다.
    """
    if not store.connected:
        raise HTTPException(status.HTTP_409_CONFLICT, "스토어 연결이 확인되지 않았습니다.")
    if store.granted_scopes and "write_products" not in store.scope_list:
        raise HTTPException(status.HTTP_409_CONFLICT, "write_products 스코프가 없어 컬렉션을 만들 수 없습니다.")

    items = [c for c in body.collections if (c.get("title") or "").strip()]
    if not items:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "만들 컬렉션이 없습니다.")

    client = await client_for(store)
    created = []
    try:
        for c in items:
            col = await client.collection_create(c["title"].strip(), (c.get("tag") or "").strip() or None)
            created.append({"title": col["title"], "handle": col["handle"], "smart": bool(c.get("tag"))})
    except ShopifyError as exc:
        done = ", ".join(x["handle"] for x in created) or "없음"
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"{exc} (여기까지는 생성됨: {done})") from exc

    return {"created": created}
