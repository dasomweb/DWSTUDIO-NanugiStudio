"""태그 엔진 (DW-ListPilot `services/tag_engine.py` 이식 — 순수 로직만).

원본의 `record_tag_usage` / `get_popular_tags`(스토어별 태그 사용 이력)는 가져오지 않았다.
`store_tag_history` 테이블이 있어야 하는데 지금 쓰는 곳이 없다. 태그 추천을 학습시킬 때
다시 붙인다.
"""

from __future__ import annotations

import re

from .presets import INDUSTRY_PRESETS

# 계절 표기는 소스마다 제각각이다(S/S, SS, Spring…). 한 축으로 모은다.
SEASON_MAP = {
    "spring": "spring",
    "ss": "spring",
    "s/s": "spring",
    "summer": "summer",
    "fall": "aw",
    "autumn": "aw",
    "a/w": "aw",
    "fw": "fw",
    "winter": "fw",
    "f/w": "fw",
}


def normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9-]", "-", value.lower().strip()).strip("-")


def normalize_season_tag(raw: str, year: str = "25") -> str:
    lowered = raw.lower()
    for key, norm in SEASON_MAP.items():
        if key in lowered:
            return f"season:{norm}{year}"
    return f"season:{normalize(raw)}"


def find_closest(value: str, options: list[str]) -> str | None:
    """프리셋 값과 느슨하게 맞춰본다. 못 맞추면 None — 호출부가 원값을 그대로 쓴다."""
    if not options:
        return None
    lowered = value.lower()
    for opt in options:
        if opt.lower() == lowered:
            return opt
    for opt in options:
        if lowered in opt.lower() or opt.lower() in lowered:
            return opt
    return None


def generate_tags(
    extracted: dict,
    industry: str,
    store_presets: dict | None = None,
) -> list[str]:
    """추출 결과의 tags_hints → `axis:value` 형식 태그 목록.

    원본은 신뢰도까지 담은 dict 를 돌려줬지만, 그 값을 쓰는 곳이 없었다(항상 0.9 고정).
    Shopify 에 넣을 문자열 목록만 돌려준다.
    """
    hints = extracted.get("tags_hints") or {}
    preset = store_presets or INDUSTRY_PRESETS.get(industry, {})
    axes = preset.get("tag_axes", {})

    tags: list[str] = []
    for axis, preset_values in axes.items():
        raw = hints.get(axis)
        if not raw:
            continue

        if axis == "season":
            tags.append(normalize_season_tag(str(raw)))
            continue

        normalized = normalize(str(raw))
        matched = find_closest(normalized, preset_values) or normalized
        if matched:
            tags.append(f"{axis}:{matched}")

    return tags
