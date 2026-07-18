"""AI 이미지 생성 — 히어로 배너 PC/모바일 (Gemini 이미지 모델).

테마의 hero 섹션은 image_1(데스크톱)과 image_1_mobile(모바일)을 따로 받는다.
같은 프롬프트를 두 비율(16:9 / 9:16)로 생성해 각각 꽂는다 — 크롭이 아니라
비율별 생성이라 모바일에서 구도가 잘리지 않는다.

google-generativeai SDK(0.8.x)는 이미지 출력 설정이 버전마다 달라서, REST 를
직접 부른다 — 엔드포인트 계약이 SDK 보다 안정적이다.
"""

from __future__ import annotations

import base64

import httpx

from ..config import get_settings

# 비율은 Gemini imageConfig 가 받는 값이어야 한다.
DESKTOP_ASPECT = "16:9"
MOBILE_ASPECT = "9:16"


class ImageGenError(RuntimeError):
    pass


def build_hero_prompt(
    description: str,
    primary: str,
    background: str,
    accent: str,
    extra: str = "",
) -> str:
    """브랜드 설명 + 확정된 팔레트 → 히어로 배경 프롬프트.

    글자는 넣지 않는다 — 헤드라인·버튼은 테마 블록이 얹는다. AI 가 그린 글자는
    번지거나 오탈자가 나고, 지역화도 안 된다.
    """
    return (
        "E-commerce hero banner background photograph. "
        f"Brand: {description.strip()[:500]}. "
        f"Color mood anchored on {primary} with {background} base and {accent} accents. "
        "Premium product-focused composition with generous negative space for overlay text. "
        "Soft studio lighting, editorial quality, photorealistic. "
        "STRICTLY NO text, NO letters, NO words, NO logos, NO watermarks anywhere in the image. "
        + (extra.strip() if extra else "")
    )


def generate_image(prompt: str, aspect_ratio: str, api_key: str, model: str) -> bytes:
    """프롬프트 → 이미지 바이트 (PNG/JPEG).

    imageConfig.aspectRatio 를 모르는 구형 모델이면 400 이 오므로, 그때는 비율 없이
    한 번 더 시도한다 (비율은 프롬프트에도 적혀 있어 근사치는 나온다).
    """
    url = (
        "https://generativelanguage.googleapis.com/v1beta/"
        f"models/{model}:generateContent?key={api_key}"
    )
    body = {
        "contents": [{"parts": [{"text": f"{prompt} Aspect ratio {aspect_ratio}."}]}],
        "generationConfig": {
            "responseModalities": ["IMAGE"],
            "imageConfig": {"aspectRatio": aspect_ratio},
        },
    }

    with httpx.Client(timeout=120) as client:
        resp = client.post(url, json=body)
        if resp.status_code == 400 and "imageConfig" in resp.text:
            del body["generationConfig"]["imageConfig"]
            resp = client.post(url, json=body)

    if resp.status_code >= 400:
        raise ImageGenError(f"이미지 생성 실패 (HTTP {resp.status_code}): {resp.text[:300]}")

    try:
        parts = resp.json()["candidates"][0]["content"]["parts"]
        for part in parts:
            inline = part.get("inlineData") or part.get("inline_data")
            if inline and inline.get("data"):
                return base64.b64decode(inline["data"])
    except (KeyError, IndexError, TypeError) as exc:
        raise ImageGenError(f"이미지 생성 응답 형식이 예상과 다릅니다: {str(resp.text)[:300]}") from exc

    raise ImageGenError("응답에 이미지가 없습니다 — 프롬프트가 안전 필터에 걸렸을 수 있습니다.")


def generate_hero_pair(
    description: str, primary: str, background: str, accent: str, extra: str = ""
) -> tuple[bytes, bytes]:
    """(데스크톱 16:9, 모바일 9:16) 이미지 쌍."""
    settings = get_settings()
    if not settings.gemini_api_key:
        raise ImageGenError("GEMINI_API_KEY 가 설정되어 있지 않습니다 — 이미지 생성을 쓸 수 없습니다.")

    prompt = build_hero_prompt(description, primary, background, accent, extra)
    desktop = generate_image(prompt, DESKTOP_ASPECT, settings.gemini_api_key, settings.gemini_image_model)
    mobile = generate_image(prompt, MOBILE_ASPECT, settings.gemini_api_key, settings.gemini_image_model)
    return desktop, mobile


def generate_one(prompt: str, aspect_ratio: str) -> bytes:
    """단건 생성 — 스토리 섹션·컬렉션 배너 등 히어로 외 용도."""
    settings = get_settings()
    if not settings.gemini_api_key:
        raise ImageGenError("GEMINI_API_KEY 가 설정되어 있지 않습니다 — 이미지 생성을 쓸 수 없습니다.")
    return generate_image(prompt, aspect_ratio, settings.gemini_api_key, settings.gemini_image_model)


def build_story_prompt(description: str, primary: str, background: str, accent: str, extra: str = "") -> str:
    """브랜드 스토리(미디어+텍스트) 섹션용 — 히어로보다 조용하고 디테일 중심."""
    return (
        "Brand story editorial photograph for an e-commerce about section. "
        f"Brand: {description.strip()[:500]}. "
        f"Color mood anchored on {primary} with {background} base and {accent} accents. "
        "Intimate detail shot — craftsmanship, materials, texture close-up. Calm, premium, photorealistic. "
        "STRICTLY NO text, NO letters, NO logos, NO watermarks. "
        + (extra.strip() if extra else "")
    )


def build_collection_prompt(collection_title: str, description: str, primary: str, accent: str) -> str:
    """컬렉션 배너용 — 카테고리가 주인공, 배경은 절제."""
    return (
        f"Product category banner photograph for '{collection_title}'. "
        f"Brand context: {description.strip()[:300]}. "
        f"Color mood: {primary} with {accent} accents. "
        "Clean studio composition focused on the product category itself, soft shadows, premium, photorealistic. "
        "STRICTLY NO text, NO letters, NO logos, NO watermarks."
    )
