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

from sqlalchemy import Column, LargeBinary
from sqlmodel import Field, SQLModel

from .capabilities import DEFAULT_MODULES, missing_scopes_for, normalize, required_scopes_for


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


class AuthType(StrEnum):
    """스토어 자격증명 방식.

    client_credentials — 앱의 client_id/secret 으로 요청 시점마다 짧은 수명의 토큰을 발급받는다.
                         나누기 스토어의 기존 테마 배포 워크플로가 쓰는 방식이며, 영구 토큰을
                         DB 에 들고 있지 않으므로 유출 리스크가 낮다. 권장.
    token              — 커스텀 앱 설치 시 나오는 영구 Admin API 토큰(shpat_…)을 그대로 저장.
                         client_credentials 를 못 쓰는 앱을 위한 대안.
    """

    client_credentials = "client_credentials"
    token = "token"


# 필요한 스코프는 스토어가 어떤 모듈을 켰느냐에 달렸다 → capabilities.py 의 레지스트리가 정한다.
#
# 축①(StoreForge) 주입에는 스코프가 필요 없다. metafieldsSet 은 "소유 리소스를 수정할 권한과
# 동일한 권한"을 요구하는데, 축①이 쓰는 메타필드의 소유자는 Shop 이고 Shopify 에는 Shop 객체용
# 스코프가 존재하지 않기 때문이다. (write_metafields 는 폐지된 이름이라 Dev Dashboard 에 넣으면
# "Contains invalid scopes" 로 거부당한다. 이걸 필수 스코프로 걸어 뒀다가 주입이 영구히 409 로
# 막힌 적이 있다 — 되풀이하지 말 것.)
#
# 반면 축②(ListPilot)와 Pricewave 는 상품을 건드리므로 write_products 가 실제로 필요하다.
# 그래서 검사는 "켠 모듈의 필수 스코프"에 대해서만 한다.


class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    name: str = ""
    password_hash: str
    role: Role = Role.owner
    is_active: bool = True
    created_at: datetime = Field(default_factory=utcnow)


class Store(SQLModel, table=True):
    """연동된 Shopify 스토어 하나 = 프로젝트 하나.

    여러 스토어를 동시에 관리하므로 자격증명은 스토어마다 따로 갖는다.
    모든 비밀값은 Fernet 으로 암호화해 저장하며, 어떤 API 응답에도 실리지 않는다.
    """

    id: int | None = Field(default=None, primary_key=True)
    name: str
    shop_domain: str = Field(unique=True, index=True)  # nanugi.myshopify.com

    auth_type: AuthType = AuthType.client_credentials

    # client_credentials 방식
    encrypted_client_id: str | None = None
    encrypted_client_secret: str | None = None

    # token 방식 (shpat_…)
    encrypted_token: str | None = None

    # 연결 테스트로 채워지는 값 — 연동이 살아있는지 보여주는 근거
    connected: bool = False
    last_checked_at: datetime | None = None
    last_error: str | None = None
    shop_name: str | None = None
    shop_plan: str | None = None
    granted_scopes: str | None = None  # 콤마 구분. 화면에서 필수 스코프 충족 여부를 보여준다.

    # 이 스토어에서 켠 통합 앱 모듈. 콤마 구분 (capabilities.MODULES 의 id).
    enabled_modules: str = ",".join(DEFAULT_MODULES)

    created_by_id: int | None = Field(default=None, foreign_key="user.id")
    created_at: datetime = Field(default_factory=utcnow)

    @property
    def scope_list(self) -> list[str]:
        return [s for s in (self.granted_scopes or "").split(",") if s]

    @property
    def module_list(self) -> list[str]:
        return normalize([m for m in (self.enabled_modules or "").split(",") if m])

    @property
    def required_scopes(self) -> list[str]:
        return required_scopes_for(self.module_list)

    @property
    def missing_scopes(self) -> list[str]:
        if not self.granted_scopes:
            return []  # 아직 확인 전 — '누락'이라고 단정하지 않는다
        return missing_scopes_for(self.module_list, self.scope_list)

    def blocked_modules(self) -> list[str]:
        """스코프가 모자라 지금 쓸 수 없는 모듈. 화면에서 이유를 보여주는 데 쓴다."""
        if not self.granted_scopes:
            return []
        return [
            mid
            for mid in self.module_list
            if missing_scopes_for([mid], self.scope_list)
        ]


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


# --- ListPilot (축②) --------------------------------------------------------------
#
# 원본(DW-ListPilot)은 UUID PK + 자체 Store 모델을 썼다. 여기서는 통합 앱의 Store(int PK)에
# 붙인다. 자격증명이 스토어마다 하나이므로 상품 초안도 스토어에 매인다.
#
# 상품은 Shopify 에 올리기 전까지 **여기서만 산다.** AI 추출 결과를 사람이 고친 뒤 등록하는 것이
# 이 제품의 핵심이라, 초안 상태를 우리 DB 가 들고 있어야 한다.


class ListingStatus(StrEnum):
    draft = "draft"  # 추출됨. 사람이 검수 중
    pushed = "pushed"  # Shopify 에 등록됨
    failed = "failed"  # 등록 시도했으나 실패


class Listing(SQLModel, table=True):
    """Shopify 에 올릴 상품 초안 하나."""

    id: int | None = Field(default=None, primary_key=True)
    store_id: int = Field(foreign_key="store.id", index=True)
    created_by_id: int | None = Field(default=None, foreign_key="user.id")

    title: str
    body_html: str = ""
    vendor: str | None = None
    product_type: str | None = None
    tags: str = ""  # 콤마 구분 (Shopify 도 같은 형식으로 받는다)

    # 추출 신뢰도. 낮은 것부터 검수하라고 화면에서 정렬 기준으로 쓴다.
    confidence: float | None = None

    status: ListingStatus = ListingStatus.draft
    shopify_product_gid: str | None = None
    error: str | None = None

    # 변형은 개수가 들쭉날쭉하고 등록 시점에 통째로 넘긴다. 표로 쪼개도 조인만 늘어난다.
    variants_json: str = "[]"  # [{option_name, option_value, price, sku, barcode, quantity, weight_kg}]

    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    pushed_at: datetime | None = None


class ListingImage(SQLModel, table=True):
    """초안 이미지. 바이트를 그대로 들고 있다가 등록 시점에 Shopify staged upload 로 올린다.

    원본은 Cloudflare R2 에 올리고 URL 만 들고 있었다. 여기서 R2 를 쓰지 않는 이유는
    이미지의 종착지가 어차피 Shopify 이기 때문이다 — 중간에 우리 버킷을 두면 공개 URL·수명주기·
    삭제 정합성을 우리가 떠안는다. 초안은 며칠 안에 등록되거나 버려지므로 DB 에 들고 있어도 된다.
    (초안이 수천 건씩 쌓이기 시작하면 그때 객체 저장소로 옮긴다.)
    """

    id: int | None = Field(default=None, primary_key=True)
    listing_id: int = Field(foreign_key="listing.id", index=True)

    position: int = 1
    alt: str = ""
    content_type: str = "image/webp"
    data: bytes = Field(sa_column=Column(LargeBinary))  # WebP 로 변환·리사이즈된 바이트

    created_at: datetime = Field(default_factory=utcnow)
