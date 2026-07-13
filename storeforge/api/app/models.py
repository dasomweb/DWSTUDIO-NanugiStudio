"""데이터 모델.

권한 모델 (3단계):
  superadmin — DASOMWEB 내부. 전 스토어 + 사용자 관리.
  admin      — 에이전시 운영자. 배정된 스토어만. 스토어 생성 가능.
  owner      — 셀러 본인. 배정된 자기 스토어만. 사용자 관리 불가.

스토어 접근은 StoreMember 로 스코핑한다. superadmin 만 이 스코핑을 우회한다.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum

from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Role(StrEnum):
    superadmin = "superadmin"
    admin = "admin"
    owner = "owner"


class RunStatus(StrEnum):
    pending = "pending"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    name: str = ""
    password_hash: str
    role: Role = Role.owner
    is_active: bool = True
    created_at: datetime = Field(default_factory=utcnow)


class Store(SQLModel, table=True):
    """연동된 Shopify 스토어 하나.

    access_token 은 Fernet 으로 암호화해 저장한다 (app/security.py).
    Phase 1 은 커스텀 앱이므로 OAuth 없이 Admin API 토큰(shpat_…)을 직접 받는다.
    Phase 3 퍼블릭 전환 시 이 필드를 OAuth 토큰으로 교체하면 나머지는 그대로 쓸 수 있다.
    """

    id: int | None = Field(default=None, primary_key=True)
    name: str
    shop_domain: str = Field(unique=True, index=True)  # nanugi.myshopify.com
    encrypted_token: str

    # 연결 테스트로 채워지는 값 — 연동이 살아있는지 보여주는 근거
    connected: bool = False
    last_checked_at: datetime | None = None
    last_error: str | None = None
    shop_name: str | None = None
    shop_plan: str | None = None

    created_by_id: int | None = Field(default=None, foreign_key="user.id")
    created_at: datetime = Field(default_factory=utcnow)


class StoreMember(SQLModel, table=True):
    """어떤 사용자가 어떤 스토어를 볼 수 있는가. superadmin 은 이 표를 무시한다."""

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    store_id: int = Field(foreign_key="store.id", index=True)
    created_at: datetime = Field(default_factory=utcnow)


class OnboardingRun(SQLModel, table=True):
    """온보딩 1회 실행 기록.

    기획안 §1.4 대로 온보딩은 1회성이지만, 무엇을 언제 주입했는지는 남겨야
    머천트가 수동 수정한 뒤 문제가 생겼을 때 원인을 가릴 수 있다.
    """

    id: int | None = Field(default=None, primary_key=True)
    store_id: int = Field(foreign_key="store.id", index=True)
    started_by_id: int | None = Field(default=None, foreign_key="user.id")

    status: RunStatus = RunStatus.pending
    brand_input_json: str = "{}"  # 사람이 확인한 입력 (3~5색 + 폰트)
    payload_json: str = "{}"  # 실제로 주입한 metafield 값
    report_json: str = "{}"  # WCAG 검증 리포트
    error: str | None = None

    started_at: datetime = Field(default_factory=utcnow)
    finished_at: datetime | None = None
