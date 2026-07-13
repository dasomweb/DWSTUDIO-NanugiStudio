"""통합 앱의 모듈 레지스트리.

스토어 연동은 **앱 하나(client_id 하나)** 로 통합한다. 그 앱이 무엇을 할 수 있는지는
여기 선언된 모듈의 합집합으로 정한다. 다만 스토어마다 켜는 모듈이 다르므로 필요한 스코프도
스토어마다 다르다 — **켜지 않은 모듈의 스코프를 이유로 막지 않는다.**

ThemePush(테마 배포)는 여기에 없다. `write_themes` 는 보호 스코프라 통합 앱에 끌어들이면
앱스토어 승인 관문이 되살아나고(기획안 §6.1 이 없애려던 바로 그것), 애초에 고객용 제품이 아니라
우리 GitHub Actions 의 배포 자격증명이다. 별도 앱으로 분리해 둔다.

배포 방식은 Custom distribution 이다. Custom 앱은 **스토어 한 곳에만** 설치할 수 있으므로
(같은 Plus 조직 또는 개발 스토어는 예외) **클라이언트 스토어마다 앱을 하나씩 만든다.**
그래서 자격증명(client_id/secret)은 Store 행마다 따로 갖는다. 나중에 Public 앱으로 전환하면
앱은 하나가 되고 스토어별 OAuth 토큰만 남는데, 그때는 AuthType.token 을 쓰면 되므로
데이터 모델을 바꾸지 않아도 된다.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Module:
    id: str
    name: str
    summary: str
    required_scopes: tuple[str, ...]
    optional_scopes: tuple[str, ...] = ()


MODULES: tuple[Module, ...] = (
    Module(
        id="storeforge",
        name="StoreForge",
        summary="브랜드 해석 → 컬러·폰트 metafield 주입 (축①)",
        # 주입 대상이 shop 소유 메타필드라 필요한 스코프가 없다. models.py 주석 참고.
        required_scopes=(),
        optional_scopes=("read_products",),  # 연결 확인용
    ),
    Module(
        id="themepush",
        name="Theme Push",
        summary="GitHub Actions → 테마 자동 배포 (`shopify theme push`)",
        # StoreForge 서버는 테마 API 를 부르지 않는다. 이 자격증명을 쓰는 것은 GitHub Actions 다.
        # 여기 모듈로 둔 이유는 "이 스토어의 앱이 테마 배포 권한까지 들고 있는가"가
        # 앱 생성 시 골라야 할 스코프를 결정하기 때문이다.
        #
        # write_themes 는 **보호 스코프**다. Custom distribution 은 승인이 없으므로 사이트별
        # 전용 앱에 넣어도 문제가 없다. 다만 나중에 Public 앱(앱스토어)으로 전환한다면
        # 이 모듈을 떼야 한다 — 안 그러면 exemption 승인 관문이 되살아난다 (기획안 §6.1).
        required_scopes=("write_themes",),
        optional_scopes=("read_themes",),
    ),
    Module(
        id="listpilot",
        name="ListPilot",
        summary="상품·컬렉션 자동 구축 — AI 상품 생성 → Shopify 등록 (축②)",
        # DW-ListPilot 의 shopify.app.toml 과 같은 집합이다.
        required_scopes=("write_products", "write_inventory"),
        optional_scopes=("read_products", "read_inventory"),
    ),
    Module(
        id="pricewave",
        name="Pricewave",
        summary="할인 코드 시각화 — 상품 페이지에 '쿠폰 적용가' 미리보기",
        # 2026-05 피벗: 가격을 쓰지 않는다. Shopify Discount 를 읽어 샵 메타필드에 요약을 넣고,
        # 테마 블록이 그걸 읽어 미리보기를 그린다. variant.price / compare_at_price 를 절대 건드리지 않는다.
        # 샵 메타필드 쓰기는 스코프가 필요 없으므로 읽기 스코프만 있으면 된다.
        required_scopes=("read_discounts",),
        optional_scopes=("read_products",),
    ),
)

MODULES_BY_ID: dict[str, Module] = {m.id: m for m in MODULES}

DEFAULT_MODULES: tuple[str, ...] = ("storeforge",)

# 앱을 만들 때 고를 스코프 = 전 모듈의 합집합.
# 스토어별로 일부 모듈만 켜더라도, 앱은 나중에 모듈을 켤 것을 대비해 이 집합으로 만들어 두는 편이
# 낫다. 스코프를 나중에 늘리려면 새 버전 Release + 앱 재설치가 필요하기 때문이다.
INSTALL_SCOPES: tuple[str, ...] = tuple(
    sorted({s for m in MODULES for s in (*m.required_scopes, *m.optional_scopes)})
)


def normalize(module_ids: list[str] | None) -> list[str]:
    """모르는 id 는 버린다. 빈 값이면 기본 모듈."""
    known = [m for m in (module_ids or []) if m in MODULES_BY_ID]
    return known or list(DEFAULT_MODULES)


def required_scopes_for(module_ids: list[str]) -> list[str]:
    return sorted({s for mid in module_ids for s in MODULES_BY_ID[mid].required_scopes})


def missing_scopes_for(module_ids: list[str], granted: list[str]) -> list[str]:
    return [s for s in required_scopes_for(module_ids) if s not in granted]
