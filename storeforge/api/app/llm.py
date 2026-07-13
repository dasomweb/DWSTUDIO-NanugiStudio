"""브랜드 해석 — 자연어 → 색 4개 + 폰트 4개 (기획안 §4.2).

LLM 의 역할은 여기서 끝난다. 315개 컬러 값을 생성시키지 않는다.
출력 표면적이 10개 미만이므로 파손 확률이 낮고, 그마저도 아래 3중으로 막는다.

  1. 구조화 출력(json_schema)  — 형태가 어긋난 응답 자체가 나올 수 없다
  2. enum 화이트리스트         — 등록되지 않은 폰트 핸들을 고를 수 없다
  3. Pydantic 검증 + 재생성    — hex 형식 위반 등은 반려하고 다시 시킨다

그리고 최종적으로 파생 엔진이 WCAG 대비를 코드로 보정하므로,
LLM 이 대비가 나쁜 색 조합을 골라도 스토어는 깨지지 않는다.
"""

from __future__ import annotations

import json
import logging

import anthropic
from pydantic import ValidationError

from .engine import fonts
from .engine.brand import PAGE_WIDTHS, BrandInput

logger = logging.getLogger(__name__)

MODEL = "claude-opus-4-8"
MAX_ATTEMPTS = 3

SYSTEM = """\
당신은 Shopify 스토어의 브랜드 디자인을 결정하는 아트 디렉터입니다.

셀러가 자연어로 설명한 브랜드를 읽고, 그 브랜드에 맞는 **핵심 색 4개와 폰트 4개**를 고릅니다.
당신이 고르는 것은 이게 전부입니다 — 버튼 hover 색, 입력창 테두리 같은 파생 값은
결정론적 엔진이 당신의 색에서 자동으로 계산하며, WCAG 대비도 코드가 보정합니다.
그러니 대비를 미세 조정하려 애쓰지 말고, **브랜드의 성격을 가장 잘 드러내는 색**에 집중하세요.

색 선택 원칙:
- primary: 브랜드의 주색. 버튼과 강조에 쓰입니다.
- background: 페이지 바탕. 대부분 흰색/오프화이트 계열이거나, 다크 브랜드면 짙은 색.
- foreground: 본문 글자색. background 와 충분히 대비되어야 합니다.
- accent: 포인트 색. primary 와 구별되는 보조색을 고르세요.

폰트 선택 원칙:
- 한국어 콘텐츠가 주가 되는 브랜드라면 한글 글리프가 있는 폰트를 body 에 쓰세요.
  (한글 미지원 폰트를 본문에 쓰면 한글이 fallback 으로 렌더되어 어색해집니다.)
- heading/accent 는 디스플레이 성격이 강한 폰트가 어울립니다.

rationale 에는 왜 이 조합인지 셀러가 이해할 수 있게 한국어 두세 문장으로 설명하세요.\
"""


def _schema() -> dict:
    """구조화 출력 스키마. 폰트는 enum 으로 화이트리스트를 강제한다."""
    handles = sorted(fonts.REGISTRY)
    color = {
        "type": "string",
        "description": "#rrggbb 형식의 6자리 hex 색 (예: #82a31a). 반드시 # 로 시작하는 6자리여야 합니다.",
    }
    font = {"type": "string", "enum": handles}

    return {
        "type": "object",
        "properties": {
            "primary": color,
            "background": color,
            "foreground": color,
            "accent": color,
            "body_font": font,
            "heading_font": font,
            "subheading_font": font,
            "accent_font": font,
            "page_width": {"type": "string", "enum": list(PAGE_WIDTHS)},
            "rationale": {
                "type": "string",
                "description": "이 조합을 고른 이유. 한국어 2~3문장.",
            },
        },
        "required": [
            "primary",
            "background",
            "foreground",
            "accent",
            "body_font",
            "heading_font",
            "subheading_font",
            "accent_font",
            "page_width",
            "rationale",
        ],
        "additionalProperties": False,
    }


def _font_catalog() -> str:
    lines = []
    for f in fonts.REGISTRY.values():
        kr = "한글 지원" if f.korean else "라틴 전용"
        lines.append(f"- {f.handle} ({f.family}, {f.category}, {kr})")
    return "\n".join(lines)


class BrandInterpretationError(RuntimeError):
    pass


def interpret(description: str, api_key: str | None = None) -> tuple[BrandInput, str]:
    """자연어 브랜드 설명 → (검증된 BrandInput, 근거 설명).

    검증에 실패하면 오류를 그대로 모델에 돌려주고 재생성시킨다.
    """
    client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()

    messages: list[dict] = [
        {
            "role": "user",
            "content": (
                f"사용 가능한 폰트 목록:\n{_font_catalog()}\n\n"
                f"브랜드 설명:\n{description.strip()}"
            ),
        }
    ]

    last_error: str | None = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=SYSTEM,
            thinking={"type": "adaptive"},
            output_config={
                "effort": "medium",
                "format": {"type": "json_schema", "schema": _schema()},
            },
            messages=messages,
        )

        if response.stop_reason == "refusal":
            raise BrandInterpretationError("모델이 요청을 거부했습니다. 설명을 바꿔서 다시 시도하세요.")

        text = "".join(b.text for b in response.content if b.type == "text")

        try:
            raw = json.loads(text)
            rationale = raw.pop("rationale", "")
            brand = BrandInput(**raw)  # ← hex 형식 등 최종 검증
            return brand, rationale

        except (json.JSONDecodeError, ValidationError, TypeError) as exc:
            last_error = str(exc)
            logger.warning("브랜드 해석 %d차 시도 실패: %s", attempt, last_error)

            if attempt == MAX_ATTEMPTS:
                break

            # 오류를 그대로 돌려주고 다시 시킨다 (기획안 §4.1 재생성 루프).
            messages.append({"role": "assistant", "content": text})
            messages.append(
                {
                    "role": "user",
                    "content": (
                        f"방금 출력이 검증에 실패했습니다:\n{last_error}\n\n"
                        "형식을 고쳐서 다시 출력하세요. 색은 반드시 #rrggbb 6자리여야 합니다."
                    ),
                }
            )

    raise BrandInterpretationError(
        f"{MAX_ATTEMPTS}회 시도했지만 유효한 브랜드를 생성하지 못했습니다: {last_error}"
    )
