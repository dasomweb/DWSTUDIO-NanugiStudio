# 상품 임포트 레시피 — 소스 사이트별 기록

**목적**: 클라이언트 스토어마다 상품을 가져오는 소스 사이트가 다르고, 사이트마다 구조가
조금씩 다르다. 한 번 알아낸 방식을 여기 기록해 다음에 같은 소스를 만나면 바로 재사용한다.

**공통 원칙**
- **영상 파일을 다운로드하거나 스크린 캡처로 대체하지 않는다.** 대신 **YouTube 링크를
  추출해 Shopify EXTERNAL_VIDEO 미디어로 첨부**한다 (`productCreateMedia`,
  mediaContentType: EXTERNAL_VIDEO, originalSource: watch URL) — 상품 갤러리에서
  재생 가능한 임베드로 뜬다. (정책 확정: 2026-07-19, A+ Straight 로 실증)
- **스펙성 데이터(제품별 커스텀 필드)는 메타필드로.** 소스 사이트의 라벨-값 행
  (HAIR MATERIAL 등)은 옵션이 아니라 스펙이다 — `productSet` 의 `metafields` 로
  namespace 별 저장. PDP 노출은 테마의 동적 소스/스펙 블록으로.
- 이미지 사용 권한은 **가져오기 전에 사용자에게 확인**받는다 (구두 확인이라도 기록).
- 개발 스토어에는 디자인 검증용 샘플만 (카테고리당 3~4개). 전량 임포트는 실스토어에서.
- 등록은 `productSet`(GraphQL) — 상품 REST API 는 폐기 경로다.
- **API 로 만든 리소스는 Online Store 채널에 미발행**이다. 컬렉션·상품 모두 REST 의
  `published: true` 로 발행해야 스토어프론트에 보인다 (write_products 로 가능,
  GraphQL 발행은 write_publications 필요).

---

## outre.com (Outre — 헤어 브랜드 공식) — 2026-07-19 검증

**스택**: WooCommerce(카테고리 목록, Flatsome 테마) + Next.js(상품 상세). JS 렌더 필수 → Playwright.

### 카테고리(제품군) 구조
`/product-category/{parent}/{child}/` 계층. 주요 라인:
`lace-wigs`(6하위) · `wigs`(converti-caps/full/half/headband/u-part…) · `weaves`(human/remi/synthetic…) ·
`braids`(pre-stretched/crochet-braid-pre-loop/braiding-hair/bulk) · `hair-pieces`(ponytails/bangs/buns/clip-ins…).
서브 브랜드: X-Pression, MyTresses, Melted Hairline, Pretty Quick 등 (`/brands/`).

### 목록 페이지 스크랩
- 상품 링크: `a[href*='/product/']` (전체 카드가 앵커). href 로 dedupe.
- 카드 제목: `.product-title` (없으면 slug 를 Title Case 로).
- 카드 텍스트에 배지·카테고리·브랜드가 붙어 나옴 (`NEWBraids • X-PRESSION - …`) — 제목으로 쓰지 말 것.

### 상품 상세 스크랩 (Next.js) — ★ 2026-07-19 정정판
- **이미지가 프록시 URL** 로 나온다: `api.outre.com/_next/image?url=<인코딩된 원본>` →
  `image?url=` 뒤를 URL-decode 해서 **원본**(`www.outre.com/wp-content/uploads/…`)을 쓸 것.
- 제목: `h1`.
- **스펙(옵션 아님)**: 본문 라벨 행에서 텍스트 추출 — `HAIR MATERIAL` / `TEXTURE` /
  `STYLE` / `COLOR SHOWN`. → Shopify 메타필드 또는 설명에 넣는다.
- **variation 은 두 축이다** (초판의 심각한 오류 — Color 하나로 잘못 모델링했었다):
  - **Color**: `AVAILABLE COLORS` 라벨 행의 **콤마 리스트가 진실의 원천**
    (예: `1,1B,2,27,30,4,425,44,613,C1B/30,C27/613,C4/30`). 버튼 텍스트 정규식 스캔은
    3자리 숫자(425/613 등)를 놓친다 — 쓰지 말 것.
  - **Length**: `LENGTHS` 라벨의 필 버튼들 (`18"`, `24"` — `/^\d+"$/`).
- **컬러 스와치 이미지 = `img[alt="color"]`**. **파일명 어간이 곧 컬러코드다**
  (`1B.jpg`, `425.jpg`, `C1B-30.jpg` — 코드의 `/` 는 파일명에서 `-`).
  → 컬러↔스와치 100% 매핑. 초판의 파일명 추측 매칭(28/131)이나 칩 클릭 캡처(느려서
  타임아웃)는 전부 불필요했다.
- **기타 이미지(갤러리)**: `img[alt^="Small image of"]` — 팩샷·모델 앞/옆/뒤컷·브랜드 카드.
  이 중 **영상 썸네일은 이미지로 넣지 말고 링크를 추출**한다. 메인 이미지: `img[alt^="Image of"]`.
- **YouTube 링크 추출법**: 정적 DOM 엔 없다 (WP youtube-embed-plus — 선택 시 로드).
  **보이는**(offsetParent≠null) 갤러리 썸네일을 순서대로 `dispatchEvent(click)` 하고
  1.5초 뒤 `iframe[src*=youtube]` 를 스캔 → `/embed/{id}` 에서 video id.
  Playwright locator.click 은 오버레이에 막히므로 dispatch 방식이어야 한다.

### Shopify 등록 매핑 — ★ 정정판
- `productSet`: title=h1, vendor='Outre', status=ACTIVE,
  **productOptions=[Color(12종), Length(18"/24")]** — variants = Color×Length 전 조합,
  files=[스와치 칩 12장 + 기타 갤러리(영상 제외)] — 원본 URL 그대로 originalSource.
- **variant 이미지 = 해당 컬러의 스와치 칩** (`productVariantAppendMedia`) —
  파일명 어간=컬러코드라 매핑이 결정론적이다. 테마 `show_variant_image: true` 와 결합하면
  outre 와 동일한 헤어 텍스처 칩 스와치 UX 가 된다.
- 스펙(HAIR MATERIAL 등)은 descriptionHtml 표 또는 메타필드로.
- 태그 규약(스마트 컬렉션과 맞물림): `category:braids`, `category:lace-wigs`, … +
  브랜드 감지(제목/브레드크럼에 X-PRESSION→`brand:x-pression`, MYTRESSES/PURPLE PACK→
  `brand:mytresses`, MELTED→`brand:melted-hairline`, PRETTY QUICK→`brand:pretty-quick`) +
  신상품 `promo:new-arrival`.
- 등록 직후 REST `PUT /products/{id}.json {"product":{"published":true}}`.
- 가격: 소스에 없음(브랜드 사이트) — placeholder 로 넣고 도매가는 사람이 책정.

### 함정 목록
1. 이미지 프록시 URL 을 그대로 쓰면 나중에 깨질 수 있다 — 반드시 원본으로 디코드.
2. 카드 innerText 를 제목으로 쓰면 배지/브랜드가 섞인다.
3. 컬러 검색 시 Shopify products query 의 `tag:category:braids` 는 콜론 때문에 실패 —
   전체 조회 후 코드에서 필터하거나 태그를 따옴표로 감쌀 것.
4. 발행 잊으면 스토어프론트 404 + 컬렉션 카드가 placeholder 로 렌더.

---

## (다음 소스 사이트 — 이 양식으로 추가)

- 스택/렌더 방식:
- 카테고리 구조:
- 목록 셀렉터:
- 상세(제목/갤러리/옵션) 셀렉터:
- 이미지 원본 규칙:
- Shopify 매핑·태그 규약:
- 함정:
