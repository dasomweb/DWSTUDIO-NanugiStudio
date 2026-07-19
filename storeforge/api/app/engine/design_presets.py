"""헤더·푸터 디자인 프리셋 — 참조 UI 킷(arbuzz/Prometheus) 기반.

홈 레이아웃(layouts.py)과 같은 철학: **테마 스키마에 실재하는 설정·블록만 조합**한다.
발명한 JSON 은 없다 — 헤더는 header 섹션의 settings 패치, 푸터는 footer/footer-utilities
섹션이 허용하는 블록(group/menu/text/logo/social-links/payment-icons/email-signup/_divider)
만으로 footer-group.json 을 새로 조립한다.

톤(라이트/다크/액센트)은 스킴 id 를 하드코딩하지 않는다 — 스토어의 settings_data 에서
색상 스킴들을 읽어 배경 휘도로 라이트/다크, 채도로 액센트를 고른다. StoreForge 가
팔레트를 주입해 스킴 색이 스토어마다 달라지기 때문이다.

적용 방식:
- 헤더: 현재 header-group.json 을 가져와 header 섹션의 settings 만 패치 (아나운스먼트 바,
  메뉴 핸들 등은 보존).
- 푸터: footer-group.json 을 프리셋으로 재조립하되, 기존 푸터에서 소셜 링크·브랜드 소개문을
  추출해 이어받는다 (프리셋을 바꿔도 스토어 데이터가 사라지지 않게).
"""

from __future__ import annotations

import json
import re
from typing import Any

# ---------------------------------------------------------------- JSON 유틸

_COMMENT_RE = re.compile(r"/\*.*?\*/", re.S)


def _parse(text: str) -> dict:
    """Shopify JSON 템플릿 파서 — 머리말 /* */ 주석을 벗기고 읽는다."""
    return json.loads(_COMMENT_RE.sub("", text))


# ---------------------------------------------------------------- 스킴 해석

def _rgb(color: str) -> tuple[float, float, float] | None:
    c = (color or "").strip()
    m = re.match(r"^#([0-9a-fA-F]{6})", c)
    if m:
        h = m.group(1)
        return int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255
    m = re.match(r"^rgba?\(([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)(?:[,\s/]+([\d.]+))?\)", c)
    if m:
        if m.group(4) is not None and float(m.group(4)) < 0.5:
            return None  # 사실상 투명 — 배경 판정에 못 쓴다
        return float(m.group(1)) / 255, float(m.group(2)) / 255, float(m.group(3)) / 255
    return None


def resolve_schemes(settings_data_text: str, brand: dict | None = None) -> dict[str, str]:
    """{light, dark, accent} 스킴 id 를 고른다.

    light = 배경 휘도 최대, dark = 최소, accent = 채도 최대(단색 흑백 제외; 없으면 dark).

    **판정 기준은 실제 렌더 색이다**: StoreForge 가 주입한 storeforge.brand 메타필드가
    .color-scheme-N CSS 를 덮어쓰므로(brand-overrides.liquid), brand 가 있으면 그 안의
    --color-background 가 settings_data 값보다 우선한다 — settings_data 만 보면
    화면과 다른 스킴을 고르게 된다 (dasomdev 에서 실증).
    """
    data = _parse(settings_data_text)
    schemes = (data.get("current") or {}).get("color_schemes") or {}
    backgrounds: dict[str, str] = {
        sid: (sc.get("settings") or {}).get("background") or ""
        for sid, sc in schemes.items()
    }
    for sc in (brand or {}).get("schemes") or []:
        bg = (sc.get("css") or {}).get("--color-background")
        if sc.get("id") and bg:
            backgrounds[sc["id"]] = bg
    scored: list[tuple[str, float, float]] = []  # (id, 휘도, 채도)
    for sid, bg in backgrounds.items():
        rgb = _rgb(bg)
        if rgb is None:
            continue
        lum = 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]
        sat = (max(rgb) - min(rgb)) / max(rgb) if max(rgb) > 0 else 0.0
        scored.append((sid, lum, sat))
    if not scored:
        return {"light": "scheme-1", "dark": "scheme-5", "accent": "scheme-5"}
    light = max(scored, key=lambda t: t[1])[0]
    dark = min(scored, key=lambda t: t[1])[0]
    saturated = [t for t in scored if t[2] > 0.25 and 0.08 < t[1] < 0.92]
    accent = max(saturated, key=lambda t: t[2])[0] if saturated else dark
    return {"light": light, "dark": dark, "accent": accent}


# ---------------------------------------------------------------- 헤더 프리셋

# 각 항목의 settings 는 header 섹션 스키마에 실재하는 id 만 쓴다.
HEADER_PRESETS: list[dict[str, Any]] = [
    {
        "id": "classic-inline",
        "name": "클래식 인라인",
        "description": "로고 왼쪽 · 메뉴 중앙 · 검색/계정/카트 오른쪽 — 표준 이커머스 헤더",
        "settings": {
            "logo_position": "left", "menu_position": "center", "menu_row": "top",
            "show_search": True, "search_display_style": "modal", "search_position": "right",
            "section_height": "standard",
        },
    },
    {
        "id": "center-logo",
        "name": "센터 로고 미니멀",
        "description": "메뉴 왼쪽 · 로고 중앙 · 계정 오른쪽 — 검색 없는 미니멀 헤더",
        "settings": {
            "logo_position": "center", "menu_position": "left", "menu_row": "top",
            "show_search": False, "section_height": "standard",
        },
    },
    {
        "id": "search-bar",
        "name": "검색바 강조",
        "description": "로고 왼쪽 · 인라인 검색창 · 메뉴는 아래 행 — 검색 중심 스토어",
        "settings": {
            "logo_position": "left", "menu_position": "center", "menu_row": "bottom",
            "show_search": True, "search_display_style": "inline", "search_position": "right",
            "search_row": "top", "section_height": "standard",
        },
    },
    {
        "id": "menu-right",
        "name": "메뉴 오른쪽",
        "description": "로고 왼쪽 · 메뉴와 검색 오른쪽 — 브랜드/포트폴리오형",
        "settings": {
            "logo_position": "left", "menu_position": "right", "menu_row": "top",
            "show_search": True, "search_display_style": "modal", "search_position": "right",
            "section_height": "standard",
        },
    },
    {
        "id": "compact",
        "name": "컴팩트 바",
        "description": "낮은 높이의 한 줄 헤더 — 로고 왼쪽 · 메뉴 오른쪽, 검색 없음",
        "settings": {
            "logo_position": "left", "menu_position": "right", "menu_row": "top",
            "show_search": False, "section_height": "compact",
        },
    },
    {
        "id": "double-row",
        "name": "더블 로우",
        "description": "유틸리티(언어/통화) 상단 행 + 로고 중앙 + 메뉴 하단 행 — 대형몰형",
        "settings": {
            "logo_position": "center", "menu_position": "center", "menu_row": "bottom",
            "show_search": True, "search_display_style": "modal", "search_position": "right",
            "search_row": "top", "show_country": True, "show_language": True,
            "localization_position": "left", "localization_row": "top",
            "section_height": "standard",
        },
    },
]


def build_header_group(current_text: str, preset_id: str, scheme_id: str) -> str:
    """현재 header-group.json 에 프리셋 settings 를 패치한 새 본문을 돌려준다."""
    preset = next((p for p in HEADER_PRESETS if p["id"] == preset_id), None)
    if preset is None:
        raise ValueError(f"모르는 헤더 프리셋: {preset_id!r}")
    group = _parse(current_text)
    header = None
    for sec in (group.get("sections") or {}).values():
        if sec.get("type") == "header":
            header = sec
            break
    if header is None:
        raise ValueError("header-group.json 에 header 섹션이 없습니다")
    settings = header.setdefault("settings", {})
    settings.update(preset["settings"])
    # 톤: 위/아래 행 모두 같은 스킴. 투명 헤더는 홈 히어로가 풀블리드일 때만 의미가
    # 있으므로 프리셋에서는 건드리지 않는다 (기존 값 보존).
    settings["color_scheme_top"] = scheme_id
    settings["color_scheme_bottom"] = scheme_id
    return json.dumps(group, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------- 푸터 카트리지

def _text(html: str, preset: str = "", **extra: Any) -> dict:
    s: dict[str, Any] = {"text": html, "width": "fit-content", "max_width": "normal"}
    if preset:
        s["type_preset"] = preset
    s.update(extra)
    return {"type": "text", "settings": s}


def _menu(handle: str, heading: str = "", layout: str = "vertical", align: str = "left") -> dict:
    return {"type": "menu", "settings": {
        "menu": handle, "heading": heading, "layout": layout,
        "horizontal_alignment": align, "heading_preset": "h6",
        "show_as_accordion": False,
    }}


def _logo(inverse: bool = False) -> dict:
    return {"type": "logo", "settings": {"inverse": inverse}}


def _social(urls: dict[str, str]) -> dict:
    return {"type": "social-links", "settings": dict(urls)}


def _payments(align: str = "center") -> dict:
    return {"type": "payment-icons", "settings": {"horizontal_alignment": align}}


def _signup(heading: str = "Subscribe to our newsletter") -> dict:
    return {"type": "email-signup", "settings": {
        "heading": heading, "heading_preset": "h5",
        "width": "custom", "custom_width": 46,
        "border_style": "underline", "style_class": "button-unstyled",
        "display_type": "arrow", "integrated_button": True,
    }}


def _divider() -> dict:
    return {"type": "_divider", "settings": {"thickness": 1, "width_percent": 100}}


def _group(children: list[dict], direction: str = "row", align: str = "space-between",
           width: str = "fill", gap: int = 24, **extra: Any) -> dict:
    blocks = {f"b{i}": b for i, b in enumerate(children)}
    settings: dict[str, Any] = {
        "content_direction": direction, "vertical_on_mobile": True,
        "gap": gap, "width": width, "inherit_color_scheme": True,
    }
    if direction == "row":
        settings["horizontal_alignment"] = align
        settings["vertical_alignment"] = "center"
    else:
        settings["horizontal_alignment_flex_direction_column"] = align
    settings.update(extra)
    return {"type": "group", "settings": settings,
            "blocks": blocks, "block_order": list(blocks.keys())}


# ---------------------------------------------------------------- 푸터 프리셋

# tone: 이 프리셋이 기본으로 쓰는 스킴 종류. 적용 시 tone 파라미터로 덮어쓸 수 있다.
FOOTER_PRESETS: list[dict[str, Any]] = [
    {"id": "trust-payments", "name": "결제 신뢰형", "tone": "light",
     "description": "중앙 '안심 쇼핑' 문구 + 결제수단 아이콘, 아래에 로고·메뉴 행"},
    {"id": "newsletter", "name": "뉴스레터형", "tone": "light",
     "description": "로고·메뉴·소셜 한 행 + 중앙 뉴스레터 구독 입력"},
    {"id": "contact-columns", "name": "연락처 컬럼형", "tone": "light",
     "description": "브랜드 소개 · Company 링크 · Contact Us · Follow Us 4컬럼"},
    {"id": "centered-social", "name": "센터 소셜형", "tone": "accent",
     "description": "컬러 배경에 로고·소셜 아이콘·메뉴를 중앙 정렬"},
    {"id": "mega-dark", "name": "메가 컬럼 다크", "tone": "dark",
     "description": "다크 배경 — 브랜드 블록 + Shop/Company 링크 컬럼 + 연락처"},
    {"id": "slim-bar", "name": "슬림 바 다크", "tone": "dark",
     "description": "다크 한 줄 — 메뉴 왼쪽 · 로고 중앙 · 소셜 오른쪽"},
    {"id": "info-payments-dark", "name": "정보+결제 다크", "tone": "dark",
     "description": "다크 컬럼 레이아웃 + 하단 결제수단·소셜 행"},
    {"id": "minimal-centered", "name": "미니멀 센터 다크", "tone": "dark",
     "description": "다크 배경 중앙 정렬 — 메뉴 한 행 · 소셜 · 결제수단"},
]


def extract_footer_carryover(current_text: str | None) -> dict[str, Any]:
    """기존 푸터에서 스토어 고유 데이터(소셜 URL, 브랜드 소개문)를 추출한다."""
    carry: dict[str, Any] = {"social": {}, "blurb": ""}
    if not current_text:
        return carry
    try:
        group = _parse(current_text)
    except (ValueError, json.JSONDecodeError):
        return carry

    def walk(blocks: dict | None) -> None:
        for b in (blocks or {}).values():
            s = b.get("settings") or {}
            if b.get("type") == "social-links" and not carry["social"]:
                urls = {k: v for k, v in s.items() if k.endswith("_url") and v}
                if urls:
                    carry["social"] = urls
            if b.get("type") == "text" and not carry["blurb"]:
                txt = s.get("text") or ""
                # 소개문으로 볼 만한 문장형 텍스트만 (헤딩/짧은 라벨 제외)
                if len(re.sub(r"<[^>]+>", "", txt)) > 40:
                    carry["blurb"] = txt
            walk(b.get("blocks"))

    for sec in (group.get("sections") or {}).values():
        walk(sec.get("blocks"))
    return carry


def build_footer_group(preset_id: str, schemes: dict[str, str],
                       carry: dict[str, Any], shop_name: str = "",
                       tone_override: str | None = None) -> str:
    """프리셋 id → footer-group.json 본문."""
    preset = next((p for p in FOOTER_PRESETS if p["id"] == preset_id), None)
    if preset is None:
        raise ValueError(f"모르는 푸터 프리셋: {preset_id!r}")
    tone = tone_override or preset["tone"]
    scheme = schemes.get(tone) or schemes["dark"]
    dark = tone in ("dark", "accent")
    social = carry.get("social") or {}
    blurb = carry.get("blurb") or "<p>Quality products, honest prices. We ship worldwide.</p>"
    contact = "<p>Mon–Fri 9am–6pm<br/>support@" + (shop_name or "example") + ".com</p>"

    footer_blocks: list[dict]
    gap = 28

    if preset_id == "trust-payments":
        footer_blocks = [
            _group([
                _text("<h4>Shop safely with us</h4>", "h4"),
                _text("<p>Your payment information is processed securely.</p>"),
                _payments("center"),
            ], "column", "center", gap=12),
            _divider(),
            _group([_logo(dark), _menu("footer", layout="horizontal", align="right")],
                   "row", "space-between"),
        ]
    elif preset_id == "newsletter":
        footer_blocks = [
            _group([_logo(dark), _menu("footer", layout="horizontal", align="center"),
                    _social(social)], "row", "space-between"),
            _divider(),
            _group([_signup()], "column", "center", gap=8),
        ]
    elif preset_id == "contact-columns":
        footer_blocks = [
            _group([
                _group([_logo(dark), _text(blurb)], "column", "flex-start",
                       width="custom", custom_width=32, gap=14),
                _menu("footer", "Company"),
                _group([_text("<h6>Contact Us</h6>", "h6"), _text(contact)],
                       "column", "flex-start", width="fit-content", gap=10),
                _group([_text("<h6>Follow Us</h6>", "h6"), _social(social)],
                       "column", "flex-start", width="fit-content", gap=10),
            ], "row", "space-between", gap=40),
        ]
    elif preset_id == "centered-social":
        footer_blocks = [
            _group([_logo(True), _social(social),
                    _menu("footer", layout="horizontal", align="center")],
                   "column", "center", gap=16),
        ]
    elif preset_id == "mega-dark":
        footer_blocks = [
            _group([
                _group([_logo(True), _text(blurb), _social(social)],
                       "column", "flex-start", width="custom", custom_width=30, gap=14),
                _menu("main-menu", "Shop"),
                _menu("footer", "Company"),
                _group([_text("<h6>Contact</h6>", "h6"), _text(contact)],
                       "column", "flex-start", width="fit-content", gap=10),
            ], "row", "space-between", gap=40),
        ]
    elif preset_id == "slim-bar":
        gap = 8
        footer_blocks = [
            _group([_menu("footer", layout="horizontal", align="left"),
                    _logo(True), _social(social)], "row", "space-between"),
        ]
    elif preset_id == "info-payments-dark":
        footer_blocks = [
            _group([
                _group([_logo(True), _text(blurb)], "column", "flex-start",
                       width="custom", custom_width=32, gap=14),
                _menu("main-menu", "Shop"),
                _menu("footer", "Company"),
            ], "row", "space-between", gap=40),
            _divider(),
            _group([_payments("flex-start"), _social(social)], "row", "space-between"),
        ]
    elif preset_id == "minimal-centered":
        footer_blocks = [
            _group([_menu("footer", layout="horizontal", align="center"),
                    _social(social), _payments("center")],
                   "column", "center", gap=18),
        ]
    else:  # pragma: no cover — FOOTER_PRESETS 와 분기 불일치 방지
        raise ValueError(f"빌더가 없는 프리셋: {preset_id!r}")

    blocks = {f"fb{i}": b for i, b in enumerate(footer_blocks)}
    footer = {
        "type": "footer",
        "settings": {
            "section_width": "page-width",
            "content_layout": "vertical",
            "gap": gap,
            "color_scheme": scheme,
            "padding-block-start": 48,
            "padding-block-end": 24,
        },
        "blocks": blocks,
        "block_order": list(blocks.keys()),
    }

    centered = preset_id in ("centered-social", "minimal-centered", "trust-payments")
    util_blocks: dict[str, dict] = {
        "copyright": {"type": "footer-copyright",
                      "settings": {"show_powered_by": False, "font_size": "0.75rem"}},
    }
    if not centered:
        util_blocks["policies"] = {"type": "footer-policy-list",
                                   "settings": {"font_size": "0.75rem"}}
    utilities = {
        "type": "footer-utilities",
        "settings": {
            "section_width": "page-width",
            "gap": 24,
            "divider_thickness": 0 if preset_id == "slim-bar" else 1,
            "color_scheme": scheme,
            "padding-block-start": 16,
            "padding-block-end": 20,
        },
        "blocks": util_blocks,
        "block_order": list(util_blocks.keys()),
    }

    # 그룹 파일은 최상위 type/name 이 필수다 — 없으면 themeFilesUpsert 가
    # "missing required key 'type'/'name'" 으로 거부한다.
    return json.dumps(
        {"type": "footer", "name": "Footer",
         "sections": {"footer": footer, "utilities": utilities},
         "order": ["footer", "utilities"]},
        ensure_ascii=False, indent=2,
    )
