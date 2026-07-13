"""스토어 연동 관리.

관리자 페이지에서 Shopify 스토어를 등록·연결 테스트·해제한다.
Phase 1(커스텀 앱)이므로 OAuth 없이 Admin API 토큰(shpat_…)을 직접 받는다.
토큰은 절대 응답에 그대로 싣지 않는다 — 마스킹해서만 보여준다.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Session, select

from ..db import get_session
from ..deps import current_user, get_store, require_roles, visible_stores
from ..models import Role, Store, StoreMember, User
from ..security import decrypt_token, encrypt_token
from ..shopify import ShopifyClient, ShopifyError, normalize_domain

router = APIRouter(prefix="/stores", tags=["stores"])


class StoreOut(BaseModel):
    id: int
    name: str
    shop_domain: str
    connected: bool
    shop_name: str | None
    shop_plan: str | None
    last_checked_at: datetime | None
    last_error: str | None


class StoreCreateIn(BaseModel):
    name: str
    shop_domain: str
    access_token: str


class StoreTokenUpdateIn(BaseModel):
    access_token: str


def _out(store: Store) -> StoreOut:
    return StoreOut(**store.model_dump())


def _client(store: Store) -> ShopifyClient:
    return ShopifyClient(store.shop_domain, decrypt_token(store.encrypted_token))


async def _refresh_connection(store: Store, session: Session) -> Store:
    """연결 테스트 결과를 스토어에 기록한다. 성공/실패 모두 남긴다."""
    try:
        info = await _client(store).verify()
        store.connected = True
        store.shop_name = info.name
        store.shop_plan = info.plan
        store.last_error = None
    except (ShopifyError, RuntimeError) as exc:
        store.connected = False
        store.last_error = str(exc)

    store.last_checked_at = datetime.now(timezone.utc)
    session.add(store)
    session.commit()
    session.refresh(store)
    return store


@router.get("", response_model=list[StoreOut])
def list_stores(
    user: User = Depends(current_user), session: Session = Depends(get_session)
) -> list[StoreOut]:
    return [_out(s) for s in visible_stores(session, user)]


@router.post("", response_model=StoreOut, status_code=201)
async def create_store(
    body: StoreCreateIn,
    user: User = Depends(require_roles(Role.superadmin, Role.admin)),
    session: Session = Depends(get_session),
) -> StoreOut:
    try:
        domain = normalize_domain(body.shop_domain)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    if session.exec(select(Store).where(Store.shop_domain == domain)).first():
        raise HTTPException(status.HTTP_409_CONFLICT, f"{domain} 은 이미 연동되어 있습니다.")

    store = Store(
        name=body.name,
        shop_domain=domain,
        encrypted_token=encrypt_token(body.access_token.strip()),
        created_by_id=user.id,
    )
    session.add(store)
    session.commit()
    session.refresh(store)

    # 등록한 사람은 자동으로 접근 권한을 갖는다 (superadmin 은 어차피 전역 접근).
    session.add(StoreMember(user_id=user.id, store_id=store.id))
    session.commit()

    store = await _refresh_connection(store, session)
    return _out(store)


@router.post("/{store_id}/test", response_model=StoreOut)
async def test_connection(
    store: Store = Depends(get_store), session: Session = Depends(get_session)
) -> StoreOut:
    return _out(await _refresh_connection(store, session))


@router.put("/{store_id}/token", response_model=StoreOut)
async def rotate_token(
    body: StoreTokenUpdateIn,
    store: Store = Depends(get_store),
    _: User = Depends(require_roles(Role.superadmin, Role.admin)),
    session: Session = Depends(get_session),
) -> StoreOut:
    store.encrypted_token = encrypt_token(body.access_token.strip())
    session.add(store)
    session.commit()
    session.refresh(store)
    return _out(await _refresh_connection(store, session))


@router.get("/{store_id}/members")
def list_members(
    store: Store = Depends(get_store),
    _: User = Depends(require_roles(Role.superadmin, Role.admin)),
    session: Session = Depends(get_session),
) -> list[dict]:
    rows = session.exec(select(StoreMember).where(StoreMember.store_id == store.id)).all()
    users = [session.get(User, r.user_id) for r in rows]
    return [
        {"id": u.id, "email": u.email, "name": u.name, "role": u.role}
        for u in users
        if u is not None
    ]


@router.post("/{store_id}/members/{user_id}", status_code=204, response_model=None)
def add_member(
    user_id: int,
    store: Store = Depends(get_store),
    _: User = Depends(require_roles(Role.superadmin, Role.admin)),
    session: Session = Depends(get_session),
) -> None:
    if not session.get(User, user_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "사용자를 찾을 수 없습니다.")
    exists = session.exec(
        select(StoreMember).where(
            StoreMember.store_id == store.id, StoreMember.user_id == user_id
        )
    ).first()
    if not exists:
        session.add(StoreMember(user_id=user_id, store_id=store.id))
        session.commit()


@router.delete("/{store_id}", status_code=204, response_model=None)
def delete_store(
    store: Store = Depends(get_store),
    _: User = Depends(require_roles(Role.superadmin)),
    session: Session = Depends(get_session),
) -> None:
    """연동 해제. 스토어의 metafield 는 건드리지 않는다 — 여기서 지우면 라이브 스토어 외관이 깨진다."""
    for m in session.exec(select(StoreMember).where(StoreMember.store_id == store.id)).all():
        session.delete(m)
    session.delete(store)
    session.commit()
