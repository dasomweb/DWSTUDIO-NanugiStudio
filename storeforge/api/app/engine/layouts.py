"""홈 레이아웃 프리셋 (기획안 §4.4 — 프리셋화 대상은 index.json 하나).

소스 테마 릴리즈 zip 의 홈 템플릿을 **변형**해서 레이아웃 변종을 만든다. 섹션 JSON 을
손으로 합성하지 않고 검증된 원본의 재배열·부분집합만 쓰므로, 결과물은 항상 유효하다.

원본 홈의 섹션 역할 (나누기 소스 기준):
  hero          — 풀블리드 히어로 배너
  section(1st)  — 에디토리얼/그리드 콘텐츠
  product-list  — 상품 그리드
  section(2nd)  — 하단 에디토리얼

zip 은 프로세스 메모리에 캐시한다 — 레이아웃 적용은 온보딩 때 한 번이라 TTL 이 필요 없고,
릴리즈가 바뀌면 재배포와 함께 캐시도 비워진다.
"""

from __future__ import annotations

import io
import json
import re
import zipfile
from dataclasses import dataclass

import httpx

from ..config import get_settings


@dataclass(frozen=True)
class Layout:
    id: str
    name: str
    description: str


# LLM 도 이 목록에서 enum 으로만 고른다 (llm.propose).
LAYOUTS: tuple[Layout, ...] = (
    Layout(
        id="editorial",
        name="에디토리얼 (기본)",
        description="히어로 배너 → 에디토리얼 → 상품 그리드 → 하단 에디토리얼. 브랜드 스토리가 강한 스토어.",
    ),
    Layout(
        id="product-first",
        name="제품 우선",
        description="히어로 배너 → 상품 그리드 → 에디토리얼. 카탈로그가 곧 첫인상인 스토어.",
    ),
    Layout(
        id="minimal",
        name="미니멀",
        description="히어로 배너 → 상품 그리드. 군더더기 없는 단일 포커스.",
    ),
    Layout(
        id="catalog",
        name="카탈로그",
        description="상품 그리드 → 에디토리얼. 히어로 없이 바로 상품으로 진입하는 도매형.",
    ),
)

LAYOUTS_BY_ID = {l.id: l for l in LAYOUTS}

_zip_cache: dict[str, bytes] = {}


def _fetch_zip(version: str | None) -> bytes:
    url = get_settings().theme_zip_upstream(version)
    if url not in _zip_cache:
        resp = httpx.get(url, follow_redirects=True, timeout=120)
        resp.raise_for_status()
        _zip_cache[url] = resp.content
    return _zip_cache[url]


def _strip_comments(raw: str) -> str:
    # Shopify 템플릿 JSON 은 /* */ 주석을 허용한다 (기획안 §2.7)
    return re.sub(r"/\*.*?\*/", "", raw, flags=re.S)


def _sanitize(node):
    """shopify:// 리소스 참조 제거 — scripts/build-source-home.py 와 같은 규칙.

    릴리즈 zip(v1.1.1+)은 이미 새니타이즈되어 있지만, 과거 버전 zip 으로 만들 수도 있으므로
    여기서도 방어적으로 벗긴다.
    """
    if isinstance(node, dict):
        return {
            k: _sanitize(v)
            for k, v in node.items()
            if not (isinstance(v, str) and v.startswith("shopify://"))
        }
    if isinstance(node, list):
        return [_sanitize(v) for v in node]
    return node


def _base_home(version: str | None) -> dict:
    z = zipfile.ZipFile(io.BytesIO(_fetch_zip(version)))
    raw = z.read("templates/index.json").decode("utf-8")
    return _sanitize(json.loads(_strip_comments(raw)))


def _classify(home: dict) -> dict[str, list[str]]:
    """섹션 id 를 역할별로 묶는다. 타입 기반이라 나누기 홈이 바뀌어도 따라간다."""
    roles: dict[str, list[str]] = {"hero": [], "products": [], "editorial": []}
    for sid in home["order"]:
        stype = home["sections"][sid]["type"]
        if stype == "hero":
            roles["hero"].append(sid)
        elif stype == "product-list":
            roles["products"].append(sid)
        else:
            roles["editorial"].append(sid)
    return roles


def build_home(layout_id: str, version: str | None = None) -> dict:
    """레이아웃 프리셋 → 그 스토어에 업서트할 templates/index.json 내용."""
    if layout_id not in LAYOUTS_BY_ID:
        raise KeyError(f"모르는 레이아웃: {layout_id!r}")

    home = _base_home(version)
    r = _classify(home)

    order_by_layout = {
        "editorial": r["hero"] + r["editorial"][:1] + r["products"] + r["editorial"][1:],
        "product-first": r["hero"] + r["products"] + r["editorial"],
        "minimal": r["hero"][:1] + r["products"][:1],
        "catalog": r["products"] + r["editorial"],
    }
    order = [sid for sid in order_by_layout[layout_id] if sid]

    if not order:
        # 원본 홈에 섹션이 하나도 분류되지 않는 건 소스가 바뀌었다는 뜻 — 원본 그대로 둔다
        return home

    return {
        "sections": {sid: home["sections"][sid] for sid in order},
        "order": order,
    }
