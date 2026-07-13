"""브랜드 페이로드 빌더 — 엔진 출력 → shop.metafields.storeforge.brand (json).

이 JSON 하나가 나누기 테마의 브랜드 외관 전체를 결정한다.
소비자는 snippets/brand-overrides.liquid 이며, 그쪽은 계산을 하지 않고 그대로 출력만 한다.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from . import fonts
from .palette import Brand, audit, build_schemes

NAMESPACE = "storeforge"
KEY = "brand"
PAYLOAD_VERSION = 1

PAGE_WIDTHS = ("narrow", "medium", "wide")

_HEX = r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$"


class BrandInput(BaseModel):
    """LLM 이 생성하고 사람이 확인하는 유일한 입력. 이보다 커지면 안 된다 (기획안 §4.2)."""

    primary: str = Field(pattern=_HEX)
    background: str = Field(pattern=_HEX)
    foreground: str = Field(pattern=_HEX)
    accent: str | None = Field(default=None, pattern=_HEX)

    body_font: str = fonts.DEFAULTS["body"]
    heading_font: str = fonts.DEFAULTS["heading"]
    subheading_font: str = fonts.DEFAULTS["subheading"]
    accent_font: str = fonts.DEFAULTS["accent"]

    page_width: str = "narrow"

    @field_validator("body_font", "heading_font", "subheading_font", "accent_font")
    @classmethod
    def _known_font(cls, v: str) -> str:
        fonts.resolve(v)  # 화이트리스트 밖이면 여기서 반려된다
        return v

    @field_validator("page_width")
    @classmethod
    def _known_width(cls, v: str) -> str:
        if v not in PAGE_WIDTHS:
            raise ValueError(f"page_width 는 {PAGE_WIDTHS} 중 하나여야 함 (받은 값: {v!r})")
        return v


def build_payload(brand_input: BrandInput) -> dict:
    """metafield 에 그대로 넣을 dict 를 만든다."""
    palette = Brand(
        primary=brand_input.primary,
        background=brand_input.background,
        foreground=brand_input.foreground,
        accent=brand_input.accent,
    )

    root, font_faces = fonts.build(
        {
            "body": brand_input.body_font,
            "heading": brand_input.heading_font,
            "subheading": brand_input.subheading_font,
            "accent": brand_input.accent_font,
        }
    )

    schemes = [{"id": s["id"], "css": s["css"]} for s in build_schemes(palette)]

    return {
        "v": PAYLOAD_VERSION,
        "root": root,
        "schemes": schemes,
        "font_faces": font_faces,
        "layout": {"page_width": brand_input.page_width},
    }


def build_report(brand_input: BrandInput) -> dict:
    """주입 전 사람이 확인할 검증 리포트. 관리자 페이지 미리보기에서 그대로 쓴다."""
    palette = Brand(
        primary=brand_input.primary,
        background=brand_input.background,
        foreground=brand_input.foreground,
        accent=brand_input.accent,
    )
    schemes = audit(palette)
    return {
        "wcag_pass": all(s["pass"] for s in schemes),
        "schemes": schemes,
        "value_count": sum(len(s["css"]) for s in build_schemes(palette)),
    }
