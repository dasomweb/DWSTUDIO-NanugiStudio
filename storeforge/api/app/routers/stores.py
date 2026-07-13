"""스토어(=프로젝트) 연동 관리.

여러 Shopify 스토어를 동시에 관리하므로 자격증명은 스토어마다 따로 갖는다.
비밀값(client_secret, 토큰)은 Fernet 으로 암호화해 저장하며, 어떤 응답에도 실리지 않는다.

기본은 client_credentials 방식이다 — 나누기의 기존 테마 배포 워크플로와 같은 패턴이고,
영구 토큰을 DB 에 들고 있지 않아도 되므로 유출 리스크가 낮다.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, model_validator
from sqlmodel import Session, select

from ..capabilities import INSTALL_SCOPES, MODULES, normalize
from ..db import get_session
from ..deps import current_user, get_store, require_roles, visible_stores
from ..models import (
    AuthType,
    OnboardingRun,
    Role,
    Store,
    StoreMember,
    User,
)
from ..security import decrypt_token, encrypt_token
from ..shopify import ShopifyClient, ShopifyError, mint_token, normalize_domain

router = APIRouter(prefix="/stores", tags=["stores"])


class StoreOut(BaseModel):
    id: int
    name: str
    shop_domain: str
    auth_type: AuthType
    connected: bool
    shop_name: str | None
    shop_plan: str | None
    last_checked_at: datetime | None
    last_error: str | None

    granted_scopes: list[str]
    missing_scopes: list[str]  # 켠 모듈이 요구하는데 없는 것 — 이게 비어야 실행이 가능하다
    required_scopes: list[str]  # 켠 모듈이 요구하는 것 (모듈에 따라 달라진다)
    install_scopes: list[str]  # 앱을 만들 때 골라야 할 전체 집합

    enabled_modules: list[str]
    blocked_modules: list[str]  # 켰지만 스코프가 모자라 지금 못 쓰는 모듈

    # 비밀값 자체는 절대 내보내지 않는다. '설정되어 있는가'만 알려준다.
    has_credentials: bool


class StoreCredentialsIn(BaseModel):
    """두 방식 중 하나. auth_type 에 따라 필요한 필드가 다르다."""

    auth_type: AuthType = AuthType.client_credentials
    client_id: str | None = None
    client_secret: str | None = None
    access_token: str | None = None

    @model_validator(mode="after")
    def _check(self) -> "StoreCredentialsIn":
        if self.auth_type == AuthType.client_credentials:
            if not (self.client_id and self.client_secret):
                raise ValueError("client_credentials 방식은 Client ID 와 Client Secret 이 모두 필요합니다.")
        else:
            if not self.access_token:
                raise ValueError("token 방식은 Admin API 액세스 토큰(shpat_…)이 필요합니다.")
        return self


class StoreCreateIn(StoreCredentialsIn):
    name: str
    shop_domain: str
    enabled_modules: list[str] | None = None


class ModuleOut(BaseModel):
    id: str
    name: str
    summary: str
    required_scopes: list[str]
    optional_scopes: list[str]


class ModulesIn(BaseModel):
    enabled_modules: list[str]


def _out(store: Store) -> StoreOut:
    return StoreOut(
        id=store.id,
        name=store.name,
        shop_domain=store.shop_domain,
        auth_type=store.auth_type,
        connected=store.connected,
        shop_name=store.shop_name,
        shop_plan=store.shop_plan,
        last_checked_at=store.last_checked_at,
        last_error=store.last_error,
        granted_scopes=store.scope_list,
        missing_scopes=store.missing_scopes,
        required_scopes=store.required_scopes,
        install_scopes=list(INSTALL_SCOPES),
        enabled_modules=store.module_list,
        blocked_modules=store.blocked_modules(),
        has_credentials=bool(
            store.encrypted_token or (store.encrypted_client_id and store.encrypted_client_secret)
        ),
    )


def _apply_credentials(store: Store, creds: StoreCredentialsIn) -> None:
    """자격증명을 암호화해 저장. 방식을 바꾸면 반대쪽 필드는 비운다."""
    store.auth_type = creds.auth_type
    if creds.auth_type == AuthType.client_credentials:
        store.encrypted_client_id = encrypt_token(creds.client_id.strip())
        store.encrypted_client_secret = encrypt_token(creds.client_secret.strip())
        store.encrypted_token = None
    else:
        store.encrypted_token = encrypt_token(creds.access_token.strip())
        store.encrypted_client_id = None
        store.encrypted_client_secret = None


async def client_for(store: Store) -> ShopifyClient:
    """스토어의 자격증명으로 Shopify 클라이언트를 만든다.

    client_credentials 면 여기서 토큰을 발급받는다 (캐시됨).
    """
    if store.auth_type == AuthType.client_credentials:
        if not (store.encrypted_client_id and store.encrypted_client_secret):
            raise ShopifyError("Client ID/Secret 이 설정되어 있지 않습니다.")
        token = await mint_token(
            store.shop_domain,
            decrypt_token(store.encrypted_client_id),
            decrypt_token(store.encrypted_client_secret),
        )
    else:
        if not store.encrypted_token:
            raise ShopifyError("액세스 토큰이 설정되어 있지 않습니다.")
        token = decrypt_token(store.encrypted_token)

    return ShopifyClient(store.shop_domain, token)


async def refresh_connection(store: Store, session: Session) -> Store:
    """연결 테스트. 성공/실패 모두 기록하고, 부여된 스코프까지 같이 읽어둔다."""
    try:
        client = await client_for(store)
        info = await client.verify()
        store.connected = True
        store.shop_name = info.name
        store.shop_plan = info.plan
        store.last_error = None

        try:
            store.granted_scopes = ",".join(await client.access_scopes())
        except ShopifyError:
            # 스코프 조회가 실패해도 연결 자체는 성공이다. 조용히 넘긴다.
            store.granted_scopes = None

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


@router.get("/modules", response_model=list[ModuleOut])
def list_modules(_: User = Depends(current_user)) -> list[ModuleOut]:
    """통합 앱이 제공하는 모듈 카탈로그. 앱을 만들 때 골라야 할 스코프의 근거이기도 하다."""
    return [
        ModuleOut(
            id=m.id,
            name=m.name,
            summary=m.summary,
            required_scopes=list(m.required_scopes),
            optional_scopes=list(m.optional_scopes),
        )
        for m in MODULES
    ]


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
        created_by_id=user.id,
        enabled_modules=",".join(normalize(body.enabled_modules)),
    )
    _apply_credentials(store, body)

    session.add(store)
    session.commit()
    session.refresh(store)

    # 등록한 사람은 자동으로 접근 권한을 갖는다 (superadmin 은 어차피 전역 접근).
    session.add(StoreMember(user_id=user.id, store_id=store.id))
    session.commit()

    return _out(await refresh_connection(store, session))


@router.post("/{store_id}/test", response_model=StoreOut)
async def test_connection(
    store: Store = Depends(get_store), session: Session = Depends(get_session)
) -> StoreOut:
    return _out(await refresh_connection(store, session))


@router.put("/{store_id}/credentials", response_model=StoreOut)
async def update_credentials(
    body: StoreCredentialsIn,
    store: Store = Depends(get_store),
    _: User = Depends(require_roles(Role.superadmin, Role.admin)),
    session: Session = Depends(get_session),
) -> StoreOut:
    """자격증명 교체 (로테이션 또는 방식 변경)."""
    _apply_credentials(store, body)
    session.add(store)
    session.commit()
    session.refresh(store)
    return _out(await refresh_connection(store, session))


@router.put("/{store_id}/modules", response_model=StoreOut)
def update_modules(
    body: ModulesIn,
    store: Store = Depends(get_store),
    _: User = Depends(require_roles(Role.superadmin, Role.admin)),
    session: Session = Depends(get_session),
) -> StoreOut:
    """이 스토어에서 켤 모듈을 정한다.

    스코프가 모자란 모듈도 켤 수 있게 둔다 — 막지 않고 '무엇이 모자란지'를 보여주는 편이,
    켜지도 못한 채 이유를 짐작하게 만드는 것보다 낫다. 실제 실행 시점에 다시 검사한다.
    """
    store.enabled_modules = ",".join(normalize(body.enabled_modules))
    session.add(store)
    session.commit()
    session.refresh(store)
    return _out(store)


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
    """연동 해제. 스토어의 metafield 는 건드리지 않는다 — 여기서 지우면 라이브 스토어 외관이 깨진다.

    자식 행(멤버십·실행 이력)을 먼저 지우고 flush 한다.
    ORM 관계를 선언하지 않았으므로 SQLAlchemy 가 삭제 순서를 알지 못한다 —
    flush 없이 한 번에 커밋하면 store 를 먼저 지우려다 FK 위반으로 죽는다.
    """
    for m in session.exec(select(StoreMember).where(StoreMember.store_id == store.id)).all():
        session.delete(m)
    for r in session.exec(select(OnboardingRun).where(OnboardingRun.store_id == store.id)).all():
        session.delete(r)
    session.flush()

    session.delete(store)
    session.commit()
