# StoreForge

AI 기반 Shopify 스토어 온보딩 자동화 (Phase 1 — 커스텀 앱).
기획: [`docs/storeforge-plan-v1.1.md`](../docs/storeforge-plan-v1.1.md)

이 디렉터리는 **테마가 아니다.** `.shopifyignore` 로 Shopify 배포에서 제외된다.

```
storeforge/
  api/   FastAPI 중계 서버 — 파생 엔진, 인증/RBAC, Shopify 주입
  web/   Next.js 관리자 페이지
```

## 설계의 핵심 두 가지

**1. LLM 은 색 3~4개만 고른다.** 나누기 테마의 컬러는 9스킴 × 35키 = **315개**다.
LLM 에게 315개를 생성시키면 반드시 깨진다. 그래서 LLM 출력을 3~4색으로 묶고,
`app/engine/palette.py` 가 결정론적으로 441개 CSS 변수를 전개하며 WCAG 대비를 자동 보정한다.
무작위 브랜드 500건 퍼징에서 WCAG 실패 0건.

**2. 테마 파일을 쓰지 않는다.** 주입 대상은 `shop.metafields.storeforge.brand` 하나뿐이다.
`write_themes`(보호 스코프)가 필요 없으므로 퍼블릭 앱 전환 시 exemption 승인 관문이 없다.
테마 쪽 소비자는 [`snippets/brand-overrides.liquid`](../snippets/brand-overrides.liquid).

> `app/shopify.py` 에 `themeFilesUpsert` 를 추가하고 싶어지면 기획안 §4.5 를 먼저 읽을 것.
> 그 순간 보호 스코프 의존이 되살아난다.

## 로컬 실행

```bash
# 백엔드 (Python 3.11+ 필요 — StrEnum)
cd api
python3.12 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
./.venv/bin/python seed.py dasomweb@gmail.com 'your-password'   # superadmin 생성
./.venv/bin/uvicorn app.main:app --port 8787

# 관리자 페이지
cd ../web
npm install
echo 'NEXT_PUBLIC_API_BASE=http://localhost:8787' > .env.local
npm run dev      # http://localhost:3000
```

## 스토어 연동 (Phase 1)

Shopify 관리자 → 설정 → 앱 및 판매 채널 → **앱 개발** → 앱 생성 →
Admin API 스코프에서 **`write_metafields`** 활성화 → 액세스 토큰(`shpat_…`) 발급.

관리자 페이지 `스토어 → + 스토어 연동` 에 도메인과 토큰을 넣으면 연결 테스트가 돌고,
토큰은 Fernet 으로 암호화되어 저장된다(응답에 절대 실리지 않음).

## 권한

| 역할 | 스토어 | 사용자 관리 |
|---|---|---|
| `superadmin` | 전체 | O |
| `admin` | 배정된 것만 (연동 생성 가능) | X |
| `owner` | 배정된 자기 것만 | X |

접근 스코핑은 `app/deps.py` 의 `get_store()` 를 **반드시** 거친다.
라우터에서 `store_id` 로 직접 조회하면 스코핑이 뚫린다.
권한 없는 스토어는 403 이 아니라 **404** 를 준다 — 존재 여부조차 노출하지 않기 위해서다.

## 아직 안 된 것

- **폰트 `.woff2` 파일 미업로드.** `app/engine/fonts.py` 의 레지스트리는 `assets/pretendard-400.woff2`
  같은 파일을 참조하지만 실제 파일이 아직 테마 `assets/` 에 없다. 업로드 전까지는 fallback 스택으로 렌더된다.
- **LLM 브랜드 해석 미연결.** 현재는 사람이 관리자 페이지에서 색을 고른다.
  자연어 → 3~4색 + 프리셋 선택 단계가 축① 의 남은 절반이다.
- **홈 레이아웃 프리셋 미제작** (기획안 §4.4).
- **축② (ListPilot 상품/컬렉션 자동 구축) 미착수.**
