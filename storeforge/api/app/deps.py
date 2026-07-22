"""인증/인가 의존성.

핵심 규칙 두 가지:
  1. 역할(Role)로 '무엇을 할 수 있는가'를 가른다.
  2. StoreMember 로 '어떤 스토어에 대해서'를 가른다. superadmin 만 2번을 우회한다.

스토어 접근 검사는 반드시 get_store() 를 통해서만 한다.
라우터에서 store_id 로 직접 조회하면 스코핑이 뚫린다.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session, select

from .db import get_session
from .models import Role, Store, StoreMember, User
from .security import decode_access_token

_bearer = HTTPBearer(auto_error=False)


def current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: Session = Depends(get_session),
) -> User:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "인증 토큰이 없습니다.")

    payload = decode_access_token(creds.credentials)
    if not payload:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "토큰이 유효하지 않거나 만료됐습니다.")

    user = session.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "사용자를 찾을 수 없거나 비활성 상태입니다.")
    return user


def require_roles(*allowed: Role):
    """지정한 역할만 통과시킨다."""

    def _guard(user: User = Depends(current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"권한이 없습니다. 필요한 역할: {', '.join(allowed)} / 현재: {user.role}",
            )
        return user

    return _guard


def can_access_store(session: Session, user: User, store_id: int) -> bool:
    if user.role == Role.superadmin:
        return True
    member = session.exec(
        select(StoreMember).where(
            StoreMember.user_id == user.id, StoreMember.store_id == store_id
        )
    ).first()
    return member is not None


def get_store(
    store_id: int,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> Store:
    """스토어를 가져오되, 접근 권한이 없으면 존재 여부조차 알려주지 않는다."""
    store = session.get(Store, store_id)
    if store is None or not can_access_store(session, user, store_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "스토어를 찾을 수 없습니다.")
    return store


def visible_stores(session: Session, user: User) -> list[Store]:
    if user.role == Role.superadmin:
        return list(session.exec(select(Store)).all())

    store_ids = session.exec(
        select(StoreMember.store_id).where(StoreMember.user_id == user.id)
    ).all()
    if not store_ids:
        return []
    return list(session.exec(select(Store).where(Store.id.in_(store_ids))).all())  # type: ignore[attr-defined]
