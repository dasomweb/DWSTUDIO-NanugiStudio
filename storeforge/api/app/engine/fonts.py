"""번들 폰트 레지스트리.

왜 번들인가 (기획안 §2.4, §4.3):
  theme-styles-variables.liquid 는 `settings.type_body_font | font_face` 를 쓴다.
  이 필터는 font_picker 가 반환하는 '폰트 객체'를 요구하는데,
  metafield 문자열("oswald_n4")을 폰트 객체로 바꾸는 Liquid 필터는 존재하지 않는다.
  → 폰트만은 metafield 로 우회할 수 없다.
  → OFL 폰트를 assets/ 에 woff2 로 번들하고 @font-face 를 직접 선언한다.
  → write_themes 보호 스코프를 완전히 벗어난다.

LLM 은 여기 등록된 핸들만 고를 수 있다 (화이트리스트). 임의 폰트명은 차단된다.

주의: 실제 .woff2 파일은 assets/ 에 업로드되어야 한다. 미업로드 시 fallback 스택으로 렌더된다.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class FontFace:
    weight: int
    style: str  # normal | italic
    asset: str  # assets/ 내 파일명


@dataclass(frozen=True)
class Font:
    handle: str
    family: str  # CSS font-family 이름
    fallback: str  # 폰트 미로드 시 대체 스택
    category: str  # display | sans | serif | mono
    korean: bool  # 한글 글리프 포함 여부 — 한인 B2B 타겟에서 결정적이다
    faces: tuple[FontFace, ...] = field(default_factory=tuple)

    @property
    def css_family(self) -> str:
        return f'"{self.family}", {self.fallback}'


SANS = "system-ui, -apple-system, 'Segoe UI', sans-serif"
SERIF = "Georgia, 'Times New Roman', serif"

REGISTRY: dict[str, Font] = {
    f.handle: f
    for f in [
        # --- 한글 지원 (한인 B2B 셀러 기본값) -----------------------------------
        Font(
            "pretendard",
            "Pretendard",
            SANS,
            "sans",
            korean=True,
            faces=(
                FontFace(400, "normal", "pretendard-400.woff2"),
                FontFace(700, "normal", "pretendard-700.woff2"),
            ),
        ),
        Font(
            "noto-sans-kr",
            "Noto Sans KR",
            SANS,
            "sans",
            korean=True,
            faces=(
                FontFace(400, "normal", "noto-sans-kr-400.woff2"),
                FontFace(700, "normal", "noto-sans-kr-700.woff2"),
            ),
        ),
        Font(
            "gmarket-sans",
            "Gmarket Sans",
            SANS,
            "display",
            korean=True,
            faces=(
                FontFace(500, "normal", "gmarket-sans-500.woff2"),
                FontFace(700, "normal", "gmarket-sans-700.woff2"),
            ),
        ),
        # --- 라틴 (현행 나누기 테마가 쓰는 조합 포함) ----------------------------
        Font(
            "bebas-neue",
            "Bebas Neue",
            SANS,
            "display",
            korean=False,
            faces=(FontFace(400, "normal", "bebas-neue-400.woff2"),),
        ),
        Font(
            "oswald",
            "Oswald",
            SANS,
            "display",
            korean=False,
            faces=(
                FontFace(400, "normal", "oswald-400.woff2"),
                FontFace(700, "normal", "oswald-700.woff2"),
            ),
        ),
        Font(
            "roboto",
            "Roboto",
            SANS,
            "sans",
            korean=False,
            faces=(
                FontFace(400, "normal", "roboto-400.woff2"),
                FontFace(700, "normal", "roboto-700.woff2"),
            ),
        ),
        Font(
            "inter",
            "Inter",
            SANS,
            "sans",
            korean=False,
            faces=(
                FontFace(400, "normal", "inter-400.woff2"),
                FontFace(700, "normal", "inter-700.woff2"),
            ),
        ),
        Font(
            "playfair-display",
            "Playfair Display",
            SERIF,
            "serif",
            korean=False,
            faces=(
                FontFace(400, "normal", "playfair-display-400.woff2"),
                FontFace(700, "normal", "playfair-display-700.woff2"),
            ),
        ),
    ]
}

# 테마의 4가지 폰트 역할 (settings: type_body_font / type_heading_font / …)
ROLES = ("body", "heading", "subheading", "accent")

DEFAULTS: dict[str, str] = {
    "body": "pretendard",
    "heading": "bebas-neue",
    "subheading": "oswald",
    "accent": "bebas-neue",
}


def resolve(handle: str) -> Font:
    font = REGISTRY.get(handle)
    if font is None:
        raise ValueError(
            f"등록되지 않은 폰트 핸들: {handle!r} — 허용: {', '.join(sorted(REGISTRY))}"
        )
    return font


def build(selection: dict[str, str]) -> tuple[dict[str, str], list[dict]]:
    """역할별 폰트 선택 → (:root CSS 변수, @font-face 목록).

    같은 폰트를 여러 역할이 공유해도 @font-face 는 한 번만 낸다.
    """
    root: dict[str, str] = {}
    faces: dict[tuple[str, int, str], dict] = {}

    for role in ROLES:
        font = resolve(selection.get(role) or DEFAULTS[role])
        regular = next((f for f in font.faces if f.weight < 600), None)
        root[f"--font-{role}--family"] = font.css_family
        root[f"--font-{role}--style"] = regular.style if regular else "normal"
        root[f"--font-{role}--weight"] = str(regular.weight if regular else 400)

        for face in font.faces:
            faces[(font.family, face.weight, face.style)] = {
                "family": font.family,
                "weight": face.weight,
                "style": face.style,
                "asset": face.asset,
            }

    return root, list(faces.values())
