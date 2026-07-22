"""저수준 색 연산.

Liquid 쪽에서는 색 연산을 일절 하지 않으므로, 모든 계산이 여기에 모인다.
sRGB / WCAG 2.x 상대 휘도 기준.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_HEX_RE = re.compile(r"^#?([0-9a-fA-F]{3,8})$")


@dataclass(frozen=True)
class Color:
    r: int  # 0-255
    g: int
    b: int
    a: float = 1.0  # 0.0-1.0

    # --- 생성 -----------------------------------------------------------------
    @staticmethod
    def parse(value: str) -> "Color":
        """#rgb / #rrggbb / #rrggbbaa 를 받는다. 나누기 테마는 #00000014 같은 8자리를 실제로 쓴다."""
        if not isinstance(value, str):
            raise ValueError(f"색이 문자열이 아님: {value!r}")
        m = _HEX_RE.match(value.strip())
        if not m:
            raise ValueError(f"hex 색으로 파싱 불가: {value!r}")
        h = m.group(1)
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        if len(h) == 6:
            return Color(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 1.0)
        if len(h) == 8:
            return Color(
                int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), int(h[6:8], 16) / 255.0
            )
        raise ValueError(f"지원하지 않는 hex 길이: {value!r}")

    # --- 출력 -----------------------------------------------------------------
    @property
    def hex(self) -> str:
        base = f"#{self.r:02x}{self.g:02x}{self.b:02x}"
        if self.a >= 0.999:
            return base
        return base + f"{round(self.a * 255):02x}"

    @property
    def rgb_triplet(self) -> str:
        """`rgb(var(--x-rgb) / var(--opacity-60))` 문법이 요구하는 'R G B' 형태."""
        return f"{self.r} {self.g} {self.b}"

    # --- 연산 -----------------------------------------------------------------
    @property
    def luminance(self) -> float:
        """WCAG 상대 휘도. 알파는 무시한다(합성은 호출자 책임)."""

        def ch(c: int) -> float:
            s = c / 255.0
            return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4

        return 0.2126 * ch(self.r) + 0.7152 * ch(self.g) + 0.0722 * ch(self.b)

    @property
    def is_dark(self) -> bool:
        return self.luminance < 0.18

    def with_alpha(self, a: float) -> "Color":
        return Color(self.r, self.g, self.b, max(0.0, min(1.0, a)))

    def mix(self, other: "Color", t: float) -> "Color":
        """t=0 → self, t=1 → other. 알파는 self 유지."""
        t = max(0.0, min(1.0, t))
        return Color(
            round(self.r + (other.r - self.r) * t),
            round(self.g + (other.g - self.g) * t),
            round(self.b + (other.b - self.b) * t),
            self.a,
        )

    def lighten(self, amount: float) -> "Color":
        return self.mix(WHITE, amount)

    def darken(self, amount: float) -> "Color":
        return self.mix(BLACK, amount)

    def shade(self, amount: float) -> "Color":
        """밝은 색은 어둡게, 어두운 색은 밝게 — hover 상태용 '한 단계 이동'."""
        return self.lighten(amount) if self.is_dark else self.darken(amount)


WHITE = Color(255, 255, 255)
BLACK = Color(0, 0, 0)


def contrast_ratio(a: Color, b: Color) -> float:
    la, lb = a.luminance, b.luminance
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def ensure_contrast(fg: Color, bg: Color, target: float = 4.5, steps: int = 24) -> Color:
    """fg 를 bg 대비 target 이상이 되도록 밀어낸다.

    LLM 재호출 없이 결정론적으로 보정한다 — 이것이 '무수정 채택률'을 지탱하는 장치다.
    bg 가 밝으면 fg 를 어둡게, 어두우면 밝게 이동시키고,
    끝까지 가도 미달이면 순수 흑/백 중 대비가 큰 쪽으로 확정한다.
    """
    if contrast_ratio(fg, bg) >= target:
        return fg

    anchor = BLACK if not bg.is_dark else WHITE
    for i in range(1, steps + 1):
        candidate = fg.mix(anchor, i / steps)
        if contrast_ratio(candidate, bg) >= target:
            return Color(candidate.r, candidate.g, candidate.b, fg.a)

    best = max((BLACK, WHITE), key=lambda c: contrast_ratio(c, bg))
    return Color(best.r, best.g, best.b, fg.a)
