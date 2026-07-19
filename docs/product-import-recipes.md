# 상품 임포트 레시피 — 소스 사이트별 기록

**목적**: 클라이언트 스토어마다 상품을 가져오는 소스 사이트가 다르고, 사이트마다 구조가
조금씩 다르다. 한 번 알아낸 방식을 여기 기록해 다음에 같은 소스를 만나면 바로 재사용한다.

**공통 원칙**
- **영상은 가져오지 않는다.** 스크린 캡처로 대체하지도 않는다 (지시: 2026-07-19).
  갤러리 수집 시 영상 썸네일·비디오 파생 이미지는 걸러낸다.
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

### 상품 상세 스크랩 (Next.js)
- **이미지가 프록시 URL** 로 나온다: `api.outre.com/_next/image?url=<인코딩된 원본>` →
  `image?url=` 뒤를 URL-decode 해서 **원본**(`www.outre.com/wp-content/uploads/…`)을 쓸 것.
- 갤러리: `img[alt^="Small image of"]` = 썸네일 세트(원본 URL 로 디코드 후 dedupe).
  메인 이미지: `img[alt^="Image of"]`.
- 제목: `h1`.
- **컬러 옵션**: 텍스트 칩 (`button/li/span` 의 innerText 가 컬러코드 패턴
  `1B`, `27`, `3T4/27613`, `T1B/30` 등). 정규식:
  `^[0-9]{1,2}[A-Z]{0,3}$|^[A-Z0-9]{1,3}/[A-Z0-9/]+$|^T[0-9]+/`
- 파일명에 컬러코드가 들어가는 경우가 있어 (`PKG_…_1B.png`) 갤러리↔컬러 매칭에
  쓸 수 있으나 **적중률 낮음** (실측 28/131). 정확한 매핑은 컬러 칩을 클릭하며 메인
  이미지 변화를 캡처해야 하는데, 상품×컬러만큼 페이지 상호작용이 필요해 느리다
  (23상품×~5컬러에 10분+ → 타임아웃). **실스토어 임포트 시 백그라운드 잡으로 돌릴 것.**

### Shopify 등록 매핑
- `productSet`: title=h1, vendor='Outre', status=ACTIVE,
  productOptions=[Color: 칩값들(≤10)], variants=컬러당 1개,
  files=[갤러리 원본 URL 그대로 originalSource — Shopify 가 직접 가져감, staged upload 불필요].
- 태그 규약(스마트 컬렉션과 맞물림): `category:braids`, `category:lace-wigs`, … +
  브랜드 감지(제목에 X-PRESSION/TWISTED UP→`brand:x-pression`, PURPLE PACK/MYTRESSES→
  `brand:mytresses`, MELTED→`brand:melted-hairline`, PRETTY QUICK→`brand:pretty-quick`) +
  신상품 `promo:new-arrival`.
- 등록 직후 REST `PUT /products/{id}.json {"product":{"published":true}}`.
- **variant 이미지 스와치**: 테마 설정 `show_variant_image: true` + variant 에 미디어 연결
  (`productVariantAppendMedia`) 하면 컬러 스와치 자리에 해당 variation 이미지가 뜬다.
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
