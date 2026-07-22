"""상품 추출·설명 생성 (DW-ListPilot `services/gemini.py` 이식).

Gemini 를 그대로 유지한다. 축①(브랜드 해석)은 Claude 구조화 출력을 쓰지만, 여기서 굳이
모델을 바꾸지 않는 이유는 이 프롬프트가 실전에서 검증된 자산이기 때문이다 — 도매 인보이스에서
여러 상품을 한 번에 뽑아내는 부분은 프롬프트를 옮기는 순간 회귀 위험이 크다.

축①과 달리 여기서는 구조화 출력(json_schema)을 강제하지 않는다. 대신 파싱에 실패하면
'인식 실패' 초안을 돌려준다 — 사람이 어차피 검수하고 등록하므로, 실패를 예외로 터뜨려
업로드 전체를 죽이는 것보다 낫다.
"""

from __future__ import annotations

import json
import re

from ...config import get_settings

EXTRACTION_SYSTEM_PROMPT = """
You are a Shopify product data extraction specialist.
Analyze the provided image or document and extract product information.

If the image contains MULTIPLE products (e.g. invoice, packing slip, catalog), return a JSON ARRAY of products.
If the image contains a SINGLE product, return a single JSON object.

Each product object must match this schema:
{
  "title": "string - product name, clean and concise",
  "vendor": "string - brand or manufacturer name",
  "product_type": "string - product category",
  "description": "string - product description in English",
  "price": "number or null",
  "sku": "string or null",
  "barcode": "string or null",
  "weight_kg": "number or null",
  "quantity": "number or null - inventory quantity if visible",
  "options": [
    { "name": "Size|Color|Material", "values": ["S","M","L"] }
  ],
  "tags_hints": {
    "category": "string or null",
    "material": "string or null",
    "style": "string or null",
    "target": "string or null - women|men|unisex|kids",
    "color": "string or null"
  },
  "confidence": "number 0-1 - overall extraction confidence"
}

Rules:
- If a field cannot be determined, use null
- product_type must be a single noun or short phrase (e.g. "Tops", "Sneakers")
- Extract ALL visible variants (sizes, colors) from the document
- For invoices/documents with multiple items: return a JSON ARRAY with each line item as a separate product
- Do NOT wrap the JSON in markdown code blocks
"""

UNRECOGNIZED = {
    "title": "Unrecognized Product",
    "vendor": None,
    "product_type": None,
    "description": "",
    "price": None,
    "sku": None,
    "barcode": None,
    "weight_kg": None,
    "quantity": None,
    "options": [],
    "tags_hints": {},
    "confidence": 0.1,
}


class GeminiNotConfigured(RuntimeError):
    pass


def _model(system_instruction: str | None = None):
    import google.generativeai as genai

    settings = get_settings()
    if not settings.gemini_api_key:
        raise GeminiNotConfigured(
            "GEMINI_API_KEY 가 설정되어 있지 않습니다 — ListPilot 의 상품 추출을 쓸 수 없습니다."
        )

    genai.configure(api_key=settings.gemini_api_key)
    return genai.GenerativeModel(
        model_name=settings.gemini_model,
        system_instruction=system_instruction,
    )


def _strip_fences(text: str) -> str:
    cleaned = re.sub(r"^```(?:json|html)?\s*", "", text.strip())
    return re.sub(r"\s*```$", "", cleaned)


def extract_from_image(image_bytes: bytes, mime_type: str) -> list[dict]:
    """이미지/PDF 페이지 한 장 → 상품 초안들.

    인보이스처럼 여러 상품이 든 문서면 배열이 온다. 호출부가 단일/다중을 신경 쓰지 않도록
    항상 리스트로 돌려준다.
    """
    response = _model(EXTRACTION_SYSTEM_PROMPT).generate_content(
        [{"mime_type": mime_type, "data": image_bytes}]
    )

    try:
        result = json.loads(_strip_fences(response.text))
    except (json.JSONDecodeError, ValueError, AttributeError):
        return [dict(UNRECOGNIZED)]

    if isinstance(result, list):
        return [r for r in result if isinstance(r, dict)] or [dict(UNRECOGNIZED)]
    if isinstance(result, dict):
        return [result]
    return [dict(UNRECOGNIZED)]


def generate_description(
    title: str,
    vendor: str | None,
    product_type: str | None,
    tags: list[str] | None,
    fallback: str | None = None,
) -> str:
    """상품 상세설명(HTML). 실패하면 기존 값을 유지한다 — 여기서 죽어서 좋을 일이 없다."""
    try:
        tags_str = ", ".join(tags) if tags else "none"
        prompt = (
            f"Write a compelling Shopify product description for: {title}"
            f" by {vendor or 'Unknown'}, category: {product_type or 'General'}."
            f" Tags: {tags_str}."
            f" Return HTML (2-3 short paragraphs with <p> tags)."
            f" Professional, concise, SEO-friendly."
        )
        return _strip_fences(_model().generate_content(prompt).text)
    except Exception:  # noqa: BLE001 — 설명 생성 실패로 등록을 막지 않는다
        return fallback or ""
