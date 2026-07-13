"""Pricewave — 할인 코드 시각화 (dasomweb/pricewave 이식).

**Pricewave 가 하지 않는 것** (2026-05 피벗에서 명시적으로 버린 것들):
  - variant.price / compare_at_price 변경
  - 쿠폰 코드 생성·관리 (Shopify 가 한다)
  - 자체 Sale 모델

**하는 것**: Shopify 의 active Discount 를 읽어 **가장 큰 할인 하나**를 골라
`shop.metafields.pricewave.active_discount` 에 요약해 넣는다. 테마 블록이 그 값을 읽어
상품 페이지에 "원가 / 쿠폰 사용 시 가격"을 그린다. 결제는 손님이 체크아웃에서 코드를
입력하면 Shopify 가 처리한다 — 우리는 아무 가격도 쓰지 않는다.

가격을 쓰지 않으므로 `write_products` 가 필요 없고, 샵 메타필드는 스코프 자체가 없다.
그래서 이 모듈의 필수 스코프는 `read_discounts` 하나뿐이다.

여기(engine)에는 순수 로직만 둔다. Shopify 왕복은 shopify.py 가 한다.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone

NAMESPACE = "pricewave"
KEY = "active_discount"

# 테마 블록(blocks/pricewave-sale-price.liquid)이 읽는 형식이다. 바꾸면 블록도 같이 고쳐야 한다.
PERCENTAGE = "PERCENTAGE"
FIXED_AMOUNT = "FIXED_AMOUNT"


@dataclass(frozen=True)
class ActiveDiscount:
    id: str
    code: str
    type: str  # PERCENTAGE | FIXED_AMOUNT
    value: float  # PERCENTAGE: 0~100 / FIXED_AMOUNT: 통화 단위 (예: 5.0)
    title: str
    starts_at: str
    ends_at: str | None

    def to_metafield(self) -> dict:
        """블록이 읽는 JSON. 키 이름은 원본(TS)의 camelCase 를 유지한다 — 블록이 그걸 읽는다."""
        d = asdict(self)
        d["startsAt"] = d.pop("starts_at")
        d["endsAt"] = d.pop("ends_at")
        return d


def _parse_dt(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def parse_discounts(nodes: list[dict], now: datetime | None = None) -> list[ActiveDiscount]:
    """discountNodes 응답 → 지금 실제로 유효한 할인들.

    Shopify 의 `status:active` 필터만 믿지 않고 기간을 다시 검사한다 — 예약된(아직 시작 전)
    할인이 섞여 들어오면 손님에게 없는 세일을 보여주게 된다.
    """
    now = now or datetime.now(timezone.utc)
    out: list[ActiveDiscount] = []

    for node in nodes:
        d = node.get("discount") or {}
        starts_at = d.get("startsAt")
        if not starts_at:
            continue

        starts = _parse_dt(starts_at)
        if starts and starts > now:
            continue  # 아직 시작 안 함
        ends = _parse_dt(d["endsAt"]) if d.get("endsAt") else None
        if ends and ends < now:
            continue  # 이미 끝남

        codes = ((d.get("codes") or {}).get("nodes")) or []
        code = codes[0].get("code") if codes else None
        if not code:
            continue  # 코드 없는 자동 할인은 미리보기 대상이 아니다

        value = ((d.get("customerGets") or {}).get("value")) or {}
        title = d.get("title") or code

        pct = value.get("percentage")
        if pct is not None:
            out.append(
                ActiveDiscount(
                    id=node["id"],
                    code=code,
                    type=PERCENTAGE,
                    value=float(pct) * 100,  # Shopify 는 0.20 을 준다 → 20 으로 저장
                    title=title,
                    starts_at=starts_at,
                    ends_at=d.get("endsAt"),
                )
            )
            continue

        amount = value.get("amount")
        if amount and amount.get("amount") is not None:
            out.append(
                ActiveDiscount(
                    id=node["id"],
                    code=code,
                    type=FIXED_AMOUNT,
                    value=float(amount["amount"]),
                    title=title,
                    starts_at=starts_at,
                    ends_at=d.get("endsAt"),
                )
            )

    return out


def pick_best(active: list[ActiveDiscount]) -> ActiveDiscount | None:
    """동시에 여러 할인이 살아 있으면 가장 큰 것 하나만 보여준다.

    정액 할인은 상품 가격을 모르면 퍼센트와 직접 비교할 수 없다. 원본과 같은 근사를 쓴다
    (정액은 절반 가중). 미리보기용 선택이라 이 정도로 충분하다.
    """
    if not active:
        return None

    def score(d: ActiveDiscount) -> float:
        return d.value if d.type == PERCENTAGE else d.value * 0.5

    return max(active, key=score)
