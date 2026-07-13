"""파생 엔진 — 브랜드 3~5색 → 나누기 테마의 315개 컬러 값.

기획안 §4.2. LLM 은 여기 들어오는 3~5색만 고르고, 확장은 전부 결정론적으로 한다.
LLM 출력 표면적을 315 → 5 미만으로 줄이는 것이 이 모듈의 존재 이유다.

나누기 테마 실측:
  스킴 9개 × 스킴당 키 35개 = 315개 값
  CSS 변수는 snippets/color-schemes.liquid 가 선언하는 이름을 그대로 덮어쓴다.
"""

from __future__ import annotations

from dataclasses import dataclass

from .color import BLACK, WHITE, Color, contrast_ratio, ensure_contrast

# 나누기 테마 settings_data.json 에 실재하는 스킴 ID (순서 유지).
# 템플릿/섹션이 이 ID 를 참조하므로 임의로 늘리거나 이름을 바꾸면 안 된다.
SCHEME_IDS: list[str] = [
    "scheme-1",
    "scheme-2",
    "scheme-3",
    "scheme-4",
    "scheme-5",
    "scheme-6",
    "scheme-7",
    "scheme-8",
    "scheme-3f8267df-3b2d-40bf-bd06-95229a6a5144",
]

# 각 스킴이 맡는 표면(surface) 역할. 머천트가 섹션마다 골라 쓰는 팔레트다.
SCHEME_ROLES: dict[str, str] = {
    "scheme-1": "light",  # 기본 배경
    "scheme-2": "light_alt",  # 살짝 톤 다운된 섹션
    "scheme-3": "dark",  # 반전 (푸터·강조 섹션)
    "scheme-4": "primary",  # 브랜드 주색 채움
    "scheme-5": "accent",  # 액센트 채움
    "scheme-6": "dark_alt",  # 반전 변주
    "scheme-7": "neutral",  # 회색 톤
    "scheme-8": "primary_deep",  # 주색 딥 톤
    "scheme-3f8267df-3b2d-40bf-bd06-95229a6a5144": "light",
}

# settings_data.json 의 스킴 설정 키 → color-schemes.liquid 가 뿜는 CSS 변수명.
SETTING_TO_CSS: dict[str, str] = {
    "background": "--color-background",
    "foreground": "--color-foreground",
    "foreground_heading": "--color-foreground-heading",
    "primary": "--color-primary",
    "primary_hover": "--color-primary-hover",
    "border": "--color-border",
    "shadow": "--color-shadow",
    "primary_button_background": "--color-primary-button-background",
    "primary_button_text": "--color-primary-button-text",
    "primary_button_border": "--color-primary-button-border",
    "primary_button_hover_background": "--color-primary-button-hover-background",
    "primary_button_hover_text": "--color-primary-button-hover-text",
    "primary_button_hover_border": "--color-primary-button-hover-border",
    "secondary_button_background": "--color-secondary-button-background",
    "secondary_button_text": "--color-secondary-button-text",
    "secondary_button_border": "--color-secondary-button-border",
    "secondary_button_hover_background": "--color-secondary-button-hover-background",
    "secondary_button_hover_text": "--color-secondary-button-hover-text",
    "secondary_button_hover_border": "--color-secondary-button-hover-border",
    "input_background": "--color-input-background",
    "input_text_color": "--color-input-text",
    "input_border_color": "--color-input-border",
    "input_hover_background": "--color-input-hover-background",
    "variant_background_color": "--color-variant-background",
    "variant_text_color": "--color-variant-text",
    "variant_border_color": "--color-variant-border",
    "variant_hover_background_color": "--color-variant-hover-background",
    "variant_hover_text_color": "--color-variant-hover-text",
    "variant_hover_border_color": "--color-variant-hover-border",
    "selected_variant_background_color": "--color-selected-variant-background",
    "selected_variant_text_color": "--color-selected-variant-text",
    "selected_variant_border_color": "--color-selected-variant-border",
    "selected_variant_hover_background_color": "--color-selected-variant-hover-background",
    "selected_variant_hover_text_color": "--color-selected-variant-hover-text",
    "selected_variant_hover_border_color": "--color-selected-variant-hover-border",
}

# 테마가 `rgb(var(--x-rgb) / var(--opacity-60))` 형태로 알파를 합성하는 키들.
# 이 키는 hex 뿐 아니라 'R G B' 트리플릿도 함께 내보내야 한다.
RGB_KEYS: set[str] = {
    "background",
    "foreground",
    "foreground_heading",
    "primary",
    "primary_hover",
    "border",
    "shadow",
    "input_text_color",
    "variant_text_color",
}

# WCAG 목표. 본문은 AA(4.5), 큰 텍스트/버튼 라벨은 3.0.
TARGET_TEXT = 4.5
TARGET_UI = 3.0


@dataclass
class Brand:
    """LLM 이 만들어내는 전부. 이보다 커지면 안 된다."""

    primary: str
    background: str
    foreground: str
    accent: str | None = None

    def resolved(self) -> tuple[Color, Color, Color, Color]:
        bg = Color.parse(self.background)
        fg = Color.parse(self.foreground)
        pr = Color.parse(self.primary)
        ac = Color.parse(self.accent) if self.accent else pr
        # 브랜드가 대비를 못 맞춰 오는 경우가 흔하다 — 입구에서 한 번 보정한다.
        fg = ensure_contrast(fg, bg, TARGET_TEXT)
        return bg, fg, pr, ac


def _brightness(c: Color) -> float:
    """Shopify `color_brightness` 와 같은 지각 밝기(0-255). 스킴별 opacity 분기에 쓰인다."""
    return (c.r * 299 + c.g * 587 + c.b * 114) / 1000


def _surface(role: str, bg: Color, fg: Color, primary: Color, accent: Color) -> tuple[Color, Color]:
    """스킴 역할 → (배경, 전경) 한 쌍. 나머지 33개 키는 이 둘에서 파생된다."""
    if role == "light":
        return bg, fg
    if role == "light_alt":
        return bg.mix(fg, 0.04), fg
    if role == "neutral":
        return bg.mix(fg, 0.08), fg
    if role == "dark":
        return fg, bg
    if role == "dark_alt":
        return fg.shade(0.10), bg
    if role == "primary":
        return primary, ensure_contrast(bg, primary, TARGET_TEXT)
    if role == "primary_deep":
        deep = primary.darken(0.28) if not primary.is_dark else primary.lighten(0.18)
        return deep, ensure_contrast(bg, deep, TARGET_TEXT)
    if role == "accent":
        return accent, ensure_contrast(fg, accent, TARGET_TEXT)
    raise ValueError(f"알 수 없는 스킴 역할: {role}")


def build_scheme(role: str, brand: Brand) -> dict[str, str]:
    """한 스킴의 35개 키를 전부 결정론적으로 채운다."""
    bg0, fg0, primary, accent = brand.resolved()
    bg, fg = _surface(role, bg0, fg0, primary, accent)

    # 표면을 뒤집거나(dark) 톤을 밀면(dark_alt) 입구에서 맞춰둔 대비가 다시 깨질 수 있다.
    # 스킴 배경이 확정된 뒤 본문 전경을 한 번 더 보정한다.
    fg = ensure_contrast(fg, bg, TARGET_TEXT)

    # 스킴 배경 위에서 주색이 보이지 않으면(예: primary 스킴) 전경색을 버튼 바탕으로 쓴다.
    accent_on_bg = primary if contrast_ratio(primary, bg) >= 1.8 else fg

    btn_bg = accent_on_bg
    btn_text = ensure_contrast(bg, btn_bg, TARGET_UI)
    btn_hover_bg = btn_bg.shade(0.14)
    btn_hover_text = ensure_contrast(btn_text, btn_hover_bg, TARGET_UI)

    sec_bg = bg.mix(fg, 0.07)
    sec_text = ensure_contrast(fg, sec_bg, TARGET_TEXT)
    sec_hover_bg = sec_bg.mix(fg, 0.07)
    sec_hover_text = ensure_contrast(sec_text, sec_hover_bg, TARGET_TEXT)

    sel_bg = accent_on_bg
    sel_text = ensure_contrast(bg, sel_bg, TARGET_UI)
    sel_hover_bg = sel_bg.shade(0.10)

    return {
        "background": bg.hex,
        "foreground": fg.hex,
        "foreground_heading": ensure_contrast(fg, bg, TARGET_TEXT).hex,
        "primary": accent_on_bg.hex,
        "primary_hover": accent_on_bg.shade(0.12).hex,
        "border": fg.with_alpha(0.12).hex,
        "shadow": (BLACK if not bg.is_dark else fg).hex,
        "primary_button_background": btn_bg.hex,
        "primary_button_text": btn_text.hex,
        "primary_button_border": btn_bg.hex,
        "primary_button_hover_background": btn_hover_bg.hex,
        "primary_button_hover_text": btn_hover_text.hex,
        "primary_button_hover_border": btn_hover_bg.hex,
        "secondary_button_background": sec_bg.hex,
        "secondary_button_text": sec_text.hex,
        "secondary_button_border": fg.with_alpha(0.16).hex,
        "secondary_button_hover_background": sec_hover_bg.hex,
        "secondary_button_hover_text": sec_hover_text.hex,
        "secondary_button_hover_border": fg.with_alpha(0.28).hex,
        "input_background": bg.hex,
        "input_text_color": fg.hex,
        "input_border_color": fg.with_alpha(0.14).hex,
        "input_hover_background": bg.mix(fg, 0.04).hex,
        "variant_background_color": bg.hex,
        "variant_text_color": fg.hex,
        "variant_border_color": fg.with_alpha(0.20).hex,
        "variant_hover_background_color": bg.mix(fg, 0.05).hex,
        "variant_hover_text_color": fg.hex,
        "variant_hover_border_color": fg.with_alpha(0.45).hex,
        "selected_variant_background_color": sel_bg.hex,
        "selected_variant_text_color": sel_text.hex,
        "selected_variant_border_color": sel_bg.hex,
        "selected_variant_hover_background_color": sel_hover_bg.hex,
        "selected_variant_hover_text_color": ensure_contrast(sel_text, sel_hover_bg, TARGET_UI).hex,
        "selected_variant_hover_border_color": sel_hover_bg.hex,
    }


def _opacity_vars(bg: Color) -> dict[str, str]:
    """color-schemes.liquid 는 배경 밝기(<64)에 따라 opacity 단계를 바꾼다. 그 분기를 그대로 재현한다."""
    dark = _brightness(bg) < 64
    return {
        "--opacity-5-15": "0.15" if dark else "0.05",
        "--opacity-10-25": "0.25" if dark else "0.1",
        "--opacity-35-55": "0.55" if dark else "0.35",
        "--opacity-40-60": "0.60" if dark else "0.40",
        "--opacity-30-60": "0.60" if dark else "0.30",
    }


def scheme_to_css(settings: dict[str, str]) -> dict[str, str]:
    """35개 설정 키 → CSS 변수 맵 (+ rgb 트리플릿, + opacity 단계)."""
    css: dict[str, str] = {}
    for key, value in settings.items():
        var = SETTING_TO_CSS.get(key)
        if var is None:
            continue  # 스키마에 없는 키는 조용히 버린다 (검증 레이어가 이미 걸렀어야 한다)
        css[var] = value
        if key in RGB_KEYS:
            css[f"{var}-rgb"] = Color.parse(value).rgb_triplet
    css.update(_opacity_vars(Color.parse(settings["background"])))
    return css


def build_schemes(brand: Brand) -> list[dict]:
    """9개 스킴 전부. brand-overrides.liquid 가 그대로 소비하는 형태로 낸다."""
    out = []
    for scheme_id in SCHEME_IDS:
        role = SCHEME_ROLES[scheme_id]
        settings = build_scheme(role, brand)
        out.append({"id": scheme_id, "role": role, "css": scheme_to_css(settings)})
    return out


# --- 검증 --------------------------------------------------------------------


def audit(brand: Brand) -> list[dict]:
    """생성된 팔레트의 WCAG 준수 여부를 스킴별로 보고한다.

    파생 엔진이 이미 보정하므로 정상 동작하면 전부 통과해야 한다.
    실패가 나오면 그건 브랜드 입력이 아니라 엔진의 버그다.
    """
    report = []
    for scheme in build_schemes(brand):
        css = scheme["css"]
        bg = Color.parse(css["--color-background"])
        checks = {
            "body_text": (Color.parse(css["--color-foreground"]), bg, TARGET_TEXT),
            "heading": (Color.parse(css["--color-foreground-heading"]), bg, TARGET_TEXT),
            "primary_button": (
                Color.parse(css["--color-primary-button-text"]),
                Color.parse(css["--color-primary-button-background"]),
                TARGET_UI,
            ),
            "secondary_button": (
                Color.parse(css["--color-secondary-button-text"]),
                Color.parse(css["--color-secondary-button-background"]),
                TARGET_TEXT,
            ),
        }
        results = {
            name: {
                "ratio": round(contrast_ratio(fg, on), 2),
                "target": target,
                "pass": contrast_ratio(fg, on) >= target,
            }
            for name, (fg, on, target) in checks.items()
        }
        report.append(
            {
                "id": scheme["id"],
                "role": scheme["role"],
                "checks": results,
                "pass": all(r["pass"] for r in results.values()),
            }
        )
    return report
