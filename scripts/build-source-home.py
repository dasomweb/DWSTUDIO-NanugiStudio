"""소스 테마 빌드용 새니타이저 — 스토어 고유 데이터를 벗겨 어느 스토어에나 설치 가능하게 만든다.

이 저장소의 템플릿·그룹 JSON 은 나누기 라이브의 것이라 세 종류의 나누기 고유 데이터를 담는다:

  1. shopify://files/... 리소스 참조 (영상·이미지) — 다른 스토어에 없어서 themeCreate 가
     해당 파일을 검증 실패로 조용히 버리고, 홈이 404 가 된다 (2026-07-14 dasomdev 실증).
  2. media_type_*: "video" — 영상 참조를 지우면 "영상 모드인데 영상 없음"이 되어 히어로가
     플레이스홀더로 렌더된다 (2026-07-18 실증). 영상은 어차피 지우므로 image 로 전환한다.
  3. 메뉴 핸들 "menu" — 나누기에만 있는 커스텀 메뉴다. 표준 핸들 main-menu 로 바꿔야
     새 스토어에서 헤더 네비게이션이 렌더된다 (2026-07-18 실증).

release-theme.yml 이 zip 을 만들기 직전에 대상 파일들에 대해 이 스크립트를 돌린다.
저장소의 원본 파일은 커밋하지 않는다 — 그건 나누기의 콘텐츠다.

주의: Shopify 템플릿 JSON 은 /* */ 주석을 허용하므로 표준 파서 전에 주석을 벗긴다 (기획안 §2.7).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

counters = {"shopify_refs": 0, "media_types": 0, "menu_handles": 0}


def strip_comments(raw: str) -> str:
    return re.sub(r"/\*.*?\*/", "", raw, flags=re.S)


def sanitize(node):
    if isinstance(node, dict):
        out = {}
        for key, value in node.items():
            if isinstance(value, str) and value.startswith("shopify://"):
                counters["shopify_refs"] += 1
                continue  # 리소스 참조 제거
            if key.startswith("media_type") and value == "video":
                counters["media_types"] += 1
                out[key] = "image"
                continue
            if key == "menu" and value == "menu":
                counters["menu_handles"] += 1
                out[key] = "main-menu"
                continue
            out[key] = sanitize(value)
        return out
    if isinstance(node, list):
        return [sanitize(v) for v in node]
    return node


def main() -> None:
    paths = [Path(p) for p in sys.argv[1:]] or [Path("templates/index.json")]
    for path in paths:
        if not path.exists():
            print(f"{path}: 없음 — 건너뜀")
            continue
        data = json.loads(strip_comments(path.read_text(encoding="utf-8")))
        path.write_text(
            json.dumps(sanitize(data), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"{path}: 처리됨")
    print(
        f"제거: shopify:// {counters['shopify_refs']}개 · "
        f"media_type video→image {counters['media_types']}개 · "
        f"메뉴 핸들 {counters['menu_handles']}개"
    )


if __name__ == "__main__":
    main()
