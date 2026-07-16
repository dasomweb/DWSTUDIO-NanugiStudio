"""메뉴(네비게이션) 자동 구성 — 온보딩 6단계.

페이지·컬렉션을 만들어도 헤더/푸터 메뉴에 걸려 있지 않으면 손님이 찾아갈 수 없다.
스토어에 실제로 존재하는 컬렉션·페이지를 읽어 메뉴 구조를 **제안**하고, 사람이 확인한
구조를 main-menu(헤더) / footer(푸터) 에 반영한다.

새 메뉴를 만들지 않고 기존 메뉴를 갱신한다 — 테마의 헤더/푸터가 기본 핸들(main-menu,
footer)을 바라보고 있어서, 갱신이면 테마 설정을 건드릴 필요가 없다.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ..deps import get_store
from ..models import Store
from ..routers.stores import client_for
from ..shopify import ShopifyError

router = APIRouter(prefix="/navigation", tags=["navigation"])
log = logging.getLogger(__name__)

# 정책 페이지는 Shopify 가 고정 URL 로 서빙한다 — 메뉴에는 HTTP 링크로 건다.
POLICY_URLS = {
    "PRIVACY_POLICY": ("Privacy Policy", "/policies/privacy-policy"),
    "TERMS_OF_SERVICE": ("Terms of Service", "/policies/terms-of-service"),
    "REFUND_POLICY": ("Refund Policy", "/policies/refund-policy"),
    "SHIPPING_POLICY": ("Shipping Policy", "/policies/shipping-policy"),
}


class NavItem(BaseModel):
    title: str
    type: str  # FRONTPAGE | COLLECTION | PAGE | HTTP
    resource_gid: str | None = None
    url: str | None = None


class PreviewOut(BaseModel):
    header: list[NavItem]
    footer: list[NavItem]
    header_menu_found: bool
    footer_menu_found: bool


class ApplyIn(BaseModel):
    header: list[NavItem] = []
    footer: list[NavItem] = []


def _guard(store: Store) -> None:
    if not store.connected:
        raise HTTPException(status.HTTP_409_CONFLICT, "스토어 연결이 확인되지 않았습니다.")
    if store.granted_scopes and "write_online_store_navigation" not in store.scope_list:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "write_online_store_navigation 스코프가 없어 메뉴를 수정할 수 없습니다 — 앱 버전에 "
            "스코프를 추가해 Release 하고 재설치한 뒤 연결 테스트를 다시 하세요.",
        )


def _find_page(pages: list[dict], *needles: str) -> dict | None:
    for p in pages:
        handle = (p.get("handle") or "").lower()
        if any(n in handle for n in needles):
            return p
    return None


@router.get("/stores/{store_id}/preview", response_model=PreviewOut)
async def preview(store: Store = Depends(get_store)) -> PreviewOut:
    """스토어의 실제 컬렉션·페이지로 메뉴 구조를 제안한다. 아무것도 쓰지 않는다."""
    if not store.connected:
        raise HTTPException(status.HTTP_409_CONFLICT, "스토어 연결이 확인되지 않았습니다.")

    try:
        client = await client_for(store)
        menus = await client.menus()
        collections = await client.collections_list()
        try:
            pages = await client.pages_list()
        except ShopifyError:
            pages = []  # read_content 가 없으면 페이지 없이 제안한다
    except ShopifyError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

    handles = {m["handle"] for m in menus}

    header: list[NavItem] = [NavItem(title="Home", type="FRONTPAGE", url="/")]
    for c in collections[:6]:  # 헤더가 넘치지 않게 — 나머지는 사람이 조절한다
        header.append(NavItem(title=c["title"], type="COLLECTION", resource_gid=c["id"]))
    for needles, fallback in ((("about",), "About"), (("contact",), "Contact")):
        page = _find_page(pages, *needles)
        if page:
            header.append(NavItem(title=page["title"], type="PAGE", resource_gid=page["id"]))

    footer: list[NavItem] = []
    for needles in (("faq",), ("shipping", "delivery")):
        page = _find_page(pages, *needles)
        if page:
            footer.append(NavItem(title=page["title"], type="PAGE", resource_gid=page["id"]))
    for title, url in POLICY_URLS.values():
        footer.append(NavItem(title=title, type="HTTP", url=url))

    return PreviewOut(
        header=header,
        footer=footer,
        header_menu_found="main-menu" in handles,
        footer_menu_found="footer" in handles,
    )


def _to_menu_items(items: list[NavItem]) -> list[dict]:
    out = []
    for it in items:
        entry: dict = {"title": it.title, "type": it.type, "items": []}
        if it.type in ("COLLECTION", "PAGE"):
            if not it.resource_gid:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST, f"'{it.title}' 항목에 resource_gid 가 없습니다."
                )
            entry["resourceId"] = it.resource_gid
        elif it.type == "HTTP":
            if not it.url:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, f"'{it.title}' 항목에 url 이 없습니다.")
            entry["url"] = it.url
        elif it.type == "FRONTPAGE":
            entry["url"] = "/"
        else:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"모르는 메뉴 타입: {it.type}")
        out.append(entry)
    return out


@router.post("/stores/{store_id}/apply")
async def apply(body: ApplyIn, store: Store = Depends(get_store)) -> dict:
    """확인된 메뉴 구조를 main-menu / footer 에 반영한다. 빈 목록은 건너뛴다."""
    _guard(store)
    if not body.header and not body.footer:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "반영할 메뉴 항목이 없습니다.")

    try:
        client = await client_for(store)
        menus = {m["handle"]: m for m in await client.menus()}

        applied = []
        for handle, items, title in (
            ("main-menu", body.header, "Main menu"),
            ("footer", body.footer, "Footer menu"),
        ):
            if not items:
                continue
            menu = menus.get(handle)
            if not menu:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    f"'{handle}' 메뉴가 스토어에 없습니다 — Shopify 관리자 > 온라인 스토어 > "
                    "메뉴에서 핸들을 확인하세요.",
                )
            await client.menu_update(menu["id"], menu.get("title") or title, _to_menu_items(items))
            applied.append(f"{handle}({len(items)}개)")
    except ShopifyError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

    log.info("[navigation] %s: %s 반영", store.shop_domain, ", ".join(applied))
    return {"applied": applied}
