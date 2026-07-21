# Outre 상품 임포트 + PDP 미디어 문제 해결 (2026-07)

dasomdev.myshopify.com(개발 스토어) 대상 작업 기록. 재사용 레시피는
[product-import-recipes.md](product-import-recipes.md) 에, 이 문서는 **이번 작업의 경위와
최종 결과**를 정리한다.

---

## 1. 상품 재빌드 (23개)

기존 22개가 잘못 등록돼 있어(옵션 1축, 메타필드·칩·영상 0) A+ Straight의 올바른 모델을
전 상품에 맞춰 다시 만들었다.

| 항목 | 이전 | 이후 |
|------|------|------|
| 변형 | Color 1축 | **Color×Length 2축, 총 322개** |
| 커스텀 필드 | 0 | **outre 메타필드 3~4종 × 23개** |
| 컬러 칩 스와치 | 0 | **308/322 변형** |
| YouTube | 썸네일이 이미지로 혼입 | 제거 후 **EXTERNAL_VIDEO 14개** |
| 발행 | 미발행 | REST `published:true` 전체 |
| 컬렉션 노출 | 카테고리 컬렉션 전부 빔 | **category 태그 부여로 정상 노출** |

- 스펙표는 상품 설명에 박지 않고 **`templates/product.json` 의 custom-liquid 블록(sf_spec)
  하나**가 `closest.product.metafields.outre` 를 읽어 전 상품 공용으로 렌더.
- 칩 없는 14개 변형(Twisted Up 10, Burmese 2, Waikiki 2)은 outre 소스에 해당 색 칩이
  아예 없는 경우 — 억지 매칭하지 않고 비워 둠(테마가 대표 이미지로 폴백).

### 스크랩에서 알아낸 것
- outre 페이지는 **두 세대**다: 구형(weave)은 `img[alt="color"]`+파일명=코드,
  신형(braids·wigs 등 대부분)은 **이미지 `alt` 자체가 컬러코드**(`alt="2T1B/27"`).
- 카테고리 컬렉션(BRAIDS/WIGS 등)은 **태그 기반 스마트 컬렉션**이라 상품에 `category:*`
  태그가 없으면 메뉴로 들어가도 빈 페이지가 된다(상품은 `/collections/all` 엔 보임).

---

## 2. PDP 미디어 히어로 문제 — 테마 3곳 수정으로 전 상품 해결

**증상**: 칩을 변형 이미지로 연결(스와치 UX)했더니, PDP 를 열면 히어로가 대표이미지가
아니라 **변형 칩**으로 떴다. 카드/추천엔 대표가 맞게 나오는데 PDP 만 달랐다.

**원하는 최종 동작 (3가지 동시 만족)**
1. 첫 로드 = 대표이미지(패키지샷)
2. 색상 클릭 = 그 색 칩으로 히어로 전환
3. 색상 원형 스와치 = 그대로 유지

### 겹쳐 있던 함정들 (순서대로 다 걸렸다)
1. **개별 상품에서 칩 detach** → 색상 스와치까지 빈 원. (스와치는 `show_variant_image` 로
   같은 칩을 그림) → 오답.
2. **`hide_variants` 로 칩을 갤러리에서 제외** → 히어로는 대표로 고쳐지지만 색상 클릭 시
   점프할 이미지가 사라져 미리보기가 죽음 → 오답.
3. **카드 링크에 `?variant=` 박힘** (`product-card.liquid` 가 `variant_to_link.url`) →
   카드로 들어오면 그 색이 선택된 채 열려 칩이 히어로. → `href="{{ product.url }}"` 로.
4. **media 배열 0번이 칩인 상품** 이 있어 `product.media` 순서로 두면 칩 히어로 →
   **`featured_media` 를 선두로 강제**.
5. **슬라이드에 `slide-id` 없음** — product 갤러리가 slideshow-slide 에 `slide_id` 를
   안 넘겨(card 갤러리만 넘김) select 매칭 불가 → **`slide_id: media.id` 추가**.
6. **`select(index)` 인덱스 어긋남** — 데스크톱/모바일 갤러리 중복(18×2=36)으로 index
   불일치 → **`slideshow.select({ id: featured_media.id })`** 로 slide-id 매칭.
7. **검증 오탐** — 슬라이드쇼는 이미지를 가로로 늘어놓고 스크롤. "가장 큰 보이는 이미지"로
   측정하면 전환 후에도 첫 이미지를 잡아 "안 바뀜"으로 보임 → `slideshow.current`(활성
   인덱스)로 확인해야 정확.

### 최종 수정 파일
| 파일 | 수정 |
|------|------|
| `snippets/product-media-gallery-content.liquid` | `sorted_media` 를 항상 `featured_media` 선두로 / slideshow-slide 에 `slide_id: media.id` |
| `assets/media-gallery.js` | `#handleVariantUpdate` 를 `replaceWith` 교체 대신 `slideshow.select({id})` 이동으로 |
| `snippets/product-card.liquid` | 카드 링크 `href` 를 `product.url`(순수 URL)로 |

테마 파일 수정이라 **23개 상품 전부 동시에** 적용된다. storeforge 스토어는
`theme_files_upsert` + `templates/product.json`(블록 `_product-media-gallery`
`hide_variants=false`)로 반영.

### 라이브 검증 (A+ Hawaiian)
| 동작 | `slideshow.current` | 히어로 |
|------|------|------|
| 첫 로드 | 0 | 패키지(대표) |
| Color 27 클릭 | 9 | 27번 칩 |
| `?variant=` 진입 | 0 | 대표 |

---

## 3. PDP 디자인 개편 (Nike 참고)

Nike PDP 레퍼런스를 참고해 dasomdev 상품 페이지 우측 패널을 개편. `templates/product.json`
의 `_product-details` 블록 `block_order` 재배치 + custom-liquid 로 반영(테마 코어 수정 없음).

| 요소 | 변경 |
|------|------|
| **가격 위치** | 옵션 아래 → **제목·리뷰 바로 아래**(block_order 에서 `price` 를 `review` 뒤로) |
| **세금 문구** | 가격 아래 "Inclusive of all taxes / (Also includes all applicable duties)" custom-liquid (`show_tax_info` 는 세금 포함 스토어에서만 떠서 문구를 직접 넣음) |
| **Length 사이즈** | 원형 → **사각 박스**. `.variant-option:not(.variant-option--swatches) .variant-option__button-label { --options-border-radius: 8px }` — Color(=`--swatches`)는 원형 유지 |
| **스펙** | 옵션 위 표 → **buy-buttons 아래 불릿 리스트**(`sf_spec` custom-liquid 를 아래로 이동 + `<ul class=sf-spec>` 재작성) |
| **배송 배지** | 트럭 아이콘 + "Free delivery on wholesale orders"(같은 custom-liquid 에 통합) |

- **핵심 함정**: variant-picker 는 Color·Length 모두 `variant-option--buttons` 를 붙이고,
  Color 만 추가로 `variant-option--swatches` 를 붙인다. 그래서 Length 만 타겟하려면
  `:not(.variant-option--swatches)` 로 걸러야 한다. 그리고 button-label 은
  `border-radius: var(--options-border-radius)`(원형 100px) 를 쓰므로 **그 변수를 재정의**해야
  이긴다(일반 `border-radius: 8px` 는 변수 우선순위에 밀린다).
- 최종 순서: 브레드크럼 → Wholesale → 제목 → 리뷰 → **가격+세금** → 설명 → Color·Length →
  구매버튼 → **스펙 불릿·배송** → Shipping/Returns 아코디언.
- 편집 전 `product.json` 을 백업(`scratchpad/product.json.backup`)하고 파이썬으로
  파싱·수정 후 `theme_files_upsert`. 리뷰 별점은 리뷰 앱/데이터 연동 시 자동 표시.

### 썸네일 레일에서 색상 칩 숨기기 (스와치로만 기능)
색상 칩이 하단 썸네일 레일에도 섞여 나왔다. 칩을 갤러리(sorted_media)에서 아예 빼면
색상 클릭 전환(select)이 깨지므로, **메인 슬라이드엔 남기고 썸네일에서만 CSS 로 숨긴다**.
칩 썸네일은 `img[alt^="swatch:"]` 로 식별된다:
```css
.slideshow-controls__thumbnail:has(img[alt^="swatch:"]),
.dialog-thumbnails-list__thumbnail:has(img[alt^="swatch:"]) { display: none !important; }
```
`sf_spec` custom-liquid 의 `<style>` 에 추가. 결과: 썸네일 레일=제품 이미지만,
색상 칩은 Color 스와치로만 기능, 색상 클릭 히어로 전환은 그대로(current 0→7 확인).

### 메인 이미지 잘림 해결 (aspect_ratio)
`_product-media-gallery` 블록의 `aspect_ratio` 가 **`1/1.25`(portrait 고정)** 이었는데,
Outre 원본 이미지는 약 **0.717:1**(670×934) 이라 `object-fit: cover` 로 상하 ~50px 씩
잘렸다(인물/패키지 상단이 크롭). **`aspect_ratio` 를 `adapt`(auto)** 로 바꿔 컨테이너가
이미지 원본 비율을 따라가게 하니(컨테이너 0.718 ≈ 원본 0.717) 잘림이 사라졌다.
`object-position` 이나 고정 비율값을 손대지 않는 근본 해결. adapt 는 상품마다 이미지
비율을 따르므로(Outre 패키지는 대부분 비슷한 비율이라 일관) 다른 상품 레이아웃도 안전하다.

---

## 4. 남은 작업
- **전체 카탈로그 임포트 미완**: outre 83개 상품의 갤러리·영상·칩은 긁었으나
  `AVAILABLE COLORS` 가 동적 로드(Next.js)라 **새 상품 ~60개의 색상 리스트를 못 가져옴**.
  색상 없이는 변형 생성 불가 → 스크랩 방식 재설계 필요.
- **브랜드/프로모 컬렉션 빔**: 소스에 `brand:*`·`promo:*` 태그가 없어 X-Pression/MyTresses/
  New Arrivals/Sale 등은 비어 있음. 브랜드는 제품명·패키지로 판별 가능, 프로모는 운영 결정.
- 위 수정들은 dasomdev(개발)에만 API 로 반영됨 — nanugi(실스토어) 반영은 별도.
