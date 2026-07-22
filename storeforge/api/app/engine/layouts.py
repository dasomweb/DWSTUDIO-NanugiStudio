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
        id="showcase",
        name="쇼핑몰 표준 (5섹션)",
        description="히어로 배너 → 컬렉션 카테고리 → 상품 그리드 → 브랜드 스토리(미디어+텍스트) → 블로그. 일반적인 쇼핑몰 정석 구성.",
    ),
    Layout(
        id="slide-commerce",
        name="슬라이드 커머스 (4섹션)",
        description="히어로 슬라이드쇼 → 컬렉션 카테고리 → 상품 그리드 → 브랜드 스토리. 첫 화면에서 여러 배너를 돌리는 프로모션형.",
    ),
    Layout(
        id="editorial",
        name="에디토리얼",
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
    """스토어 고유 데이터 제거 — scripts/build-source-home.py 와 같은 규칙.

    릴리즈 zip(v1.1.2+)은 이미 새니타이즈되어 있지만, 과거 버전 zip 으로 만들 수도 있으므로
    여기서도 방어적으로 처리한다: shopify:// 참조 제거, 영상 미디어 모드는 image 로
    (영상은 지워지므로 video 모드로 두면 히어로가 플레이스홀더로 렌더된다).
    """
    if isinstance(node, dict):
        out = {}
        for k, v in node.items():
            if isinstance(v, str) and v.startswith("shopify://"):
                continue
            if k.startswith("media_type") and v == "video":
                out[k] = "image"
                continue
            out[k] = _sanitize(v)
        return out
    if isinstance(node, list):
        return [_sanitize(v) for v in node]
    return node


def _base_home(version: str | None) -> dict:
    z = zipfile.ZipFile(io.BytesIO(_fetch_zip(version)))
    raw = z.read("templates/index.json").decode("utf-8")
    return _sanitize(json.loads(_strip_comments(raw)))


# themeFilesUpsert 는 richtext 설정값의 최상위 노드가 p/ul/ol/h1~h6 이어야 한다며 거부한다.
# 섹션 schema preset 의 기본값에는 맨몸 텍스트가 흔해서, 스키마에서 richtext 타입 설정을
# 찾아 <p> 로 감싼다 (dasomdev UAT 에서 실증된 거부 사례).
_RICHTEXT_OK_RE = re.compile(r"\s*<(p|ul|ol|h[1-6])\b", re.I)


def _schema_of(z: zipfile.ZipFile, path: str) -> dict | None:
    try:
        src = z.read(path).decode("utf-8")
    except KeyError:
        return None
    m = re.search(r"{%\s*schema\s*%}(.*?){%\s*endschema\s*%}", src, re.S)
    if not m:
        return None
    try:
        return json.loads(_strip_comments(m.group(1)))
    except json.JSONDecodeError:
        return None


def _richtext_ids(schema: dict | None) -> set[str]:
    if not schema:
        return set()
    return {
        s["id"]
        for s in schema.get("settings", [])
        if s.get("type") == "richtext" and s.get("id")
    }


def _wrap_richtext(settings: dict | None, rich_ids: set[str]) -> None:
    for key, value in (settings or {}).items():
        if key in rich_ids and isinstance(value, str) and value and not _RICHTEXT_OK_RE.match(value):
            settings[key] = f"<p>{value}</p>"


def _locale_of(z: zipfile.ZipFile) -> dict:
    """테마 기본 로케일(en.default.json).

    이 파일은 /* */ 블록 주석에 더해 **// 라인 주석**까지 담고 있다 (실측). 라인 시작
    주석만 지운다 — 문자열 값 안의 "https://…" 를 건드리면 안 된다. 파싱 실패 시 빈 dict 를
    돌려주면 t: 해석이 전부 실패해 텍스트 설정이 통째로 삭제되므로(스토리 섹션 텍스트
    소실로 실증), 여기가 조용히 무너지면 안 된다.
    """
    merged: dict = {}
    # preset 이 참조하는 html_defaults 는 schema 로케일에 산다 (실측). 콘텐츠 로케일과 병합한다.
    for name in ("locales/en.default.json", "locales/en.default.schema.json"):
        try:
            raw = z.read(name).decode("utf-8-sig")
            raw = _strip_comments(raw)
            raw = re.sub(r"^\s*//.*$", "", raw, flags=re.M)
            raw = re.sub(r",(\s*[}\]])", r"\1", raw)  # 주석 제거로 생기는 트레일링 콤마
            merged.update(json.loads(raw))
        except (KeyError, json.JSONDecodeError):
            continue
    return merged


def _resolve_t(value: str, locale: dict) -> str | None:
    """'t:html_defaults.shop_by_collection' → 로케일의 실제 문자열. 못 찾으면 None.

    테마 에디터는 '섹션 추가' 때 preset 의 t: 키를 해석해 실문자열을 넣는다. 우리는 preset 을
    직접 템플릿에 박으므로 같은 해석을 여기서 해야 한다 — 안 하면 스토어프론트에
    't:html_defaults...' 가 그대로 노출된다 (dasomdev 스크린샷으로 실증).
    """
    node = locale
    for part in value[2:].split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node if isinstance(node, str) else None


def _polish_settings(settings: dict | None, rich_ids: set[str], locale: dict) -> None:
    for key in list((settings or {}).keys()):
        value = settings[key]
        if not isinstance(value, str):
            continue
        if value.startswith("t:"):
            resolved = _resolve_t(value, locale)
            if resolved is None:
                # 해석 실패 → 키를 지운다. 설정이 없으면 렌더 시 schema default(t: 포함)가
                # Shopify 쪽에서 정상 해석된다.
                del settings[key]
                continue
            settings[key] = value = resolved
        if key in rich_ids and value and not _RICHTEXT_OK_RE.match(value):
            settings[key] = f"<p>{value}</p>"


def _fix_richtext(z: zipfile.ZipFile, entry: dict) -> None:
    """섹션 엔트리(블록 트리 포함)의 t: 번역 키 해석 + richtext 정규화."""
    locale = _locale_of(z)
    _polish_settings(
        entry.get("settings"), _richtext_ids(_schema_of(z, f"sections/{entry['type']}.liquid")), locale
    )

    def walk(blocks: dict | None) -> None:
        for block in (blocks or {}).values():
            btype = block.get("type")
            if btype:
                # 블록 타입명이 곧 파일명이다 (공개 블록 text → blocks/text.liquid, 비공개 _slide → blocks/_slide.liquid)
                _polish_settings(
                    block.get("settings"), _richtext_ids(_schema_of(z, f"blocks/{btype}.liquid")), locale
                )
            walk(block.get("blocks"))

    walk(entry.get("blocks"))


def bind_collections(home: dict, handles: list[str]) -> int:
    """collection-list 섹션에 실제 컬렉션 핸들을 바인딩한다. 반환: 바인딩된 섹션 수.

    collection_list 설정이 비어 있으면 섹션은 placeholder 데모 카드를 그린다 —
    스토어에 있는 컬렉션을 채워야 카드(와 우리가 건 배너 이미지)가 실제로 나온다.
    """
    if not handles:
        return 0
    count = 0
    for sid in home["order"]:
        sec = home["sections"][sid]
        if sec["type"] == "collection-list":
            sec.setdefault("settings", {})["collection_list"] = handles[:6]
            count += 1
    return count


# 레이아웃 재적용이 지워서는 안 되는, 이미지 파이프라인이 심어 둔 설정들.
_HERO_KEEP = ("image_1", "image_1_mobile", "media_type_1", "media_type_1_mobile")


def merge_media(new_home: dict, current_home: dict | None) -> None:
    """기존 홈의 히어로/스토리 이미지를 새 레이아웃으로 이월한다.

    레이아웃은 zip 기본값에서 다시 조립되므로, 이월하지 않으면 '홈 구성 반영'을 누를 때마다
    생성해 둔 이미지가 전부 placeholder 로 되돌아간다.
    """
    if not current_home:
        return

    def first(home: dict, stype: str) -> dict | None:
        return next(
            (home["sections"][s] for s in home["order"] if home["sections"][s]["type"] == stype),
            None,
        )

    cur_hero, new_hero = first(current_home, "hero"), first(new_home, "hero")
    if cur_hero and new_hero:
        keep = {k: v for k, v in (cur_hero.get("settings") or {}).items() if k in _HERO_KEEP}
        new_hero.setdefault("settings", {}).update(keep)

    cur_story, new_story = first(current_home, "media-with-content"), first(new_home, "media-with-content")
    if cur_story and new_story:
        def media_block(sec: dict) -> dict | None:
            for b in (sec.get("blocks") or {}).values():
                if "_media" in (b.get("type") or ""):
                    return b
            return None

        cb, nb = media_block(cur_story), media_block(new_story)
        if cb and nb:
            keep = {k: v for k, v in (cb.get("settings") or {}).items() if k in ("image", "media_type")}
            nb.setdefault("settings", {}).update(keep)


def _section_from_preset(version: str | None, section_type: str) -> dict | None:
    """섹션의 {% schema %} preset[0] → 템플릿 섹션 엔트리.

    테마 에디터가 "섹션 추가"를 누를 때 쓰는 바로 그 기본값이므로, 테마 작성자가 검증한
    유효한 구성이 보장된다. 이 테마의 preset 은 이미 템플릿 형식(settings/blocks/block_order)
    그대로라 변환이 필요 없다. preset 이 없는 섹션이면 None.
    """
    z = zipfile.ZipFile(io.BytesIO(_fetch_zip(version)))
    try:
        src = z.read(f"sections/{section_type}.liquid").decode("utf-8")
    except KeyError:
        return None
    m = re.search(r"{%\s*schema\s*%}(.*?){%\s*endschema\s*%}", src, re.S)
    if not m:
        return None
    schema = json.loads(_strip_comments(m.group(1)))
    presets = schema.get("presets") or []
    if not presets:
        return None
    preset = _sanitize(presets[0])
    entry: dict = {"type": section_type}
    for key in ("settings", "blocks", "block_order"):
        if key in preset:
            entry[key] = preset[key]
    _fix_richtext(z, entry)
    return entry


def theme_version_in_zip(version: str | None = None) -> str | None:
    """zip 에 스탬프된 theme_version. GitHub API(레이트리밋 있음) 없이 버전을 알아낸다."""
    try:
        z = zipfile.ZipFile(io.BytesIO(_fetch_zip(version)))
        schema = json.loads(_strip_comments(z.read("config/settings_schema.json").decode("utf-8")))
        tv = schema[0].get("theme_version")
        return f"v{tv}" if tv else None
    except Exception:  # noqa: BLE001 — 버전 표기는 보조 정보다. 여기서 설치를 막지 않는다
        return None


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
    """레이아웃 프리셋 → 그 스토어에 업서트할 templates/index.json 내용.

    두 가지 재료만 쓴다: ① 원본 홈의 검증된 섹션(재배열·부분집합) ② 섹션 schema 의
    preset(테마 에디터의 '섹션 추가' 기본값). 섹션 JSON 을 손으로 지어내지 않는다.
    """
    if layout_id not in LAYOUTS_BY_ID:
        raise KeyError(f"모르는 레이아웃: {layout_id!r}")

    home = _base_home(version)
    r = _classify(home)

    sections: dict[str, dict] = {}
    order: list[str] = []

    def use(sid: str) -> None:
        sections[sid] = home["sections"][sid]
        order.append(sid)

    def synth(section_type: str, sid: str) -> None:
        entry = _section_from_preset(version, section_type)
        if entry:  # preset 없는 섹션이면 조용히 건너뛴다 — 구성이 한 칸 줄어들 뿐이다
            sections[sid] = entry
            order.append(sid)

    if layout_id == "showcase":
        # 쇼핑몰 정석 5섹션: 히어로 → 카테고리 → 상품 → 브랜드 스토리 → 블로그
        for sid in r["hero"][:1]:
            use(sid)
        synth("collection-list", "sf_collections")
        for sid in r["products"][:1]:
            use(sid)
        synth("media-with-content", "sf_story")
        synth("featured-blog-posts", "sf_blog")
    elif layout_id == "slide-commerce":
        synth("slideshow", "sf_slideshow")
        synth("collection-list", "sf_collections")
        for sid in r["products"][:1]:
            use(sid)
        synth("media-with-content", "sf_story")
    else:
        order_by_layout = {
            "editorial": r["hero"] + r["editorial"][:1] + r["products"] + r["editorial"][1:],
            "product-first": r["hero"] + r["products"] + r["editorial"],
            "minimal": r["hero"][:1] + r["products"][:1],
            "catalog": r["products"] + r["editorial"],
        }
        for sid in order_by_layout[layout_id]:
            use(sid)

    if not order:
        # 아무것도 조립되지 않는 건 소스가 바뀌었다는 뜻 — 원본 그대로 둔다
        return home

    # 기본 레이아웃 폭은 1400px 콘텐츠(page-width + 전역 narrow)로 통일한다.
    # 나누기 원본·섹션 preset 일부가 full-width 라 그대로 두면 스토어가 풀블리드로 나온다.
    # 풀블리드를 원하는 섹션은 머천트가 에디터에서 개별적으로 바꾼다.
    for sid in order:
        sections[sid].setdefault("settings", {})["section_width"] = "page-width"

    return {"sections": sections, "order": order}
