"""로그인 / 내 정보 / 사용자 관리(superadmin 전용)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlmodel import Session, select

from ..db import get_session
from ..deps import current_user, require_roles
from ..models import Role, StoreMember, User
from ..security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserOut"


class UserOut(BaseModel):
    id: int
    email: str
    name: str
    role: Role
    is_active: bool


class UserCreateIn(BaseModel):
    email: EmailStr
    name: str = ""
    password: str
    role: Role = Role.owner
    store_ids: list[int] = []


TokenOut.model_rebuild()


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, session: Session = Depends(get_session)) -> TokenOut:
    user = session.exec(select(User).where(User.email == body.email)).first()
    # 이메일 존재 여부를 노출하지 않도록 실패 메시지를 통일한다.
    if not user or not verify_password(body.password, user.password_hash) or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "이메일 또는 비밀번호가 올바르지 않습니다.")

    return TokenOut(
        access_token=create_access_token(user.id, user.role),
        user=UserOut(**user.model_dump()),
    )


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)) -> UserOut:
    return UserOut(**user.model_dump())


@router.get("/users", response_model=list[UserOut])
def list_users(
    _: User = Depends(require_roles(Role.superadmin)),
    session: Session = Depends(get_session),
) -> list[UserOut]:
    return [UserOut(**u.model_dump()) for u in session.exec(select(User)).all()]


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(
    body: UserCreateIn,
    _: User = Depends(require_roles(Role.superadmin)),
    session: Session = Depends(get_session),
) -> UserOut:
    if session.exec(select(User).where(User.email == body.email)).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "이미 존재하는 이메일입니다.")
    if len(body.password) < 8:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "비밀번호는 8자 이상이어야 합니다.")

    user = User(
        email=body.email,
        name=body.name,
        password_hash=hash_password(body.password),
        role=body.role,
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    # 아래 commit() 이 user 인스턴스를 expire 시키므로 응답을 먼저 확정한다.
    out = UserOut(**user.model_dump())

    for store_id in body.store_ids:
        session.add(StoreMember(user_id=user.id, store_id=store_id))
    session.commit()

    return out


@router.delete("/users/{user_id}", status_code=204, response_model=None)
def deactivate_user(
    user_id: int,
    actor: User = Depends(require_roles(Role.superadmin)),
    session: Session = Depends(get_session),
) -> None:
    if user_id == actor.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "자기 자신은 비활성화할 수 없습니다.")
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "사용자를 찾을 수 없습니다.")
    user.is_active = False
    session.add(user)
    session.commit()
