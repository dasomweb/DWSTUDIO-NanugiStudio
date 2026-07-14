"""소스 테마용 홈 템플릿 빌드 — templates/index.json 에서 스토어 고유 리소스를 벗겨낸다.

이 저장소의 index.json 은 나누기 라이브의 홈이라 shopify://files/... 같은
**나누기 스토어에만 존재하는 리소스**를 참조한다. 그 참조가 남은 채로 다른 스토어에
themeCreate 하면 Shopify 가 검증 실패로 이 파일만 조용히 버리고, 홈이 404 가 된다
(2026-07-14 dasomdev 에서 실증).

그래서 릴리즈 zip 을 만들 때(release-theme.yml) 이 스크립트로 shopify:// 참조를 제거한
중립 홈을 담는다. 저장소의 index.json 자체는 건드리지 않는다 — 그건 나누기의 콘텐츠다.

주의: Shopify 템플릿 JSON 은 /* */ 주석을 허용하므로 표준 파서 전에 주석을 벗긴다
(기획안 §2.7). 출력은 주석 없는 표준 JSON 이다.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


def strip_comments(raw: str) -> str:
    return re.sub(r"/\*.*?\*/", "", raw, flags=re.S)


def sanitize(node):
    """settings 트리에서 shopify:// 값을 가진 키를 제거한다.

    영상·이미지·파일 참조가 대상이다. 컬렉션/상품 핸들은 그대로 둔다 — 없는 핸들은
    빈 섹션으로 렌더될 뿐 파일 검증을 깨지 않고, 스토어에 같은 핸들이 생기면 살아난다.
    """
    if isinstance(node, dict):
        return {
            k: sanitize(v)
            for k, v in node.items()
            if not (isinstance(v, str) and v.startswith("shopify://"))
        }
    if isinstance(node, list):
        return [sanitize(v) for v in node]
    return node


def main() -> None:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "templates/index.json")
    data = json.loads(strip_comments(path.read_text(encoding="utf-8")))

    before = json.dumps(data)
    cleaned = sanitize(data)
    removed = before.count("shopify://")

    path.write_text(
        json.dumps(cleaned, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"{path}: shopify:// 참조 {removed}개 제거")


if __name__ == "__main__":
    main()
