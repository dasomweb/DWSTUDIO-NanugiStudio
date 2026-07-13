# 통합 앱 — Shopify 스토어 연동 사양

**최종 갱신**: 2026-07-13
**관련**: [storeforge-plan-v1.1.md](storeforge-plan-v1.1.md) · [storeforge-status.md](storeforge-status.md) · [THEME-DEPLOY-WIKI.md](THEME-DEPLOY-WIKI.md)

DWSTUDIO 의 세 제품을 **Shopify 앱 하나**로 묶어 스토어에 연동한다.
앱은 하나지만 스토어마다 켜는 모듈이 다르고, 필요한 스코프도 그에 따라 달라진다.

---

## 1. 무엇을 묶고 무엇을 묶지 않았나

| 제품 | 통합 | 하는 일 | 필수 스코프 |
|---|---|---|---|
| **StoreForge** (축①) | ✅ | 브랜드 해석 → 컬러·폰트 metafield 주입 | **없음** |
| **ListPilot** (축②) | ✅ | AI 상품 생성 → Shopify 등록 | `write_products`, `write_inventory` |
| **Pricewave** | ✅ | 할인 코드 시각화 (쿠폰 적용가 미리보기) | `read_discounts` |
| **ThemePush** | ❌ **제외** | GitHub Actions → 테마 배포 | `write_themes` (보호) |

스코프는 각 원본 저장소의 `shopify.app.toml` 에서 가져왔다 (`dasomweb/DW-ListPilot`, `dasomweb/pricewave`).

### Pricewave 가 `write_products` 를 쓰지 않는 이유

2026-05 피벗으로 **가격 실행 스택을 통째로 버렸다.** 이제 `variant.price` / `compare_at_price` 를
건드리지 않는다. Shopify 의 active 할인 코드를 **읽어서** 샵 메타필드에 요약을 넣고, 테마 블록이
그걸 읽어 "원가 / 쿠폰 사용 시 가격"을 그린다. 결제는 손님이 체크아웃에서 코드를 입력하면
Shopify 가 처리한다. 그래서 읽기 스코프(`read_discounts`) 하나면 된다.

### ThemePush 를 제외한 이유

1. **`write_themes` 는 보호 스코프다.** 통합 앱에 끌어들이면 기획안 §6.1 이 metafield 경로로 없애 놓은
   **앱스토어 승인 관문이 나머지 제품에까지 되살아난다.**
2. **제품이 아니라 CI 자격증명이다.** 우리 저장소 → 우리 테마를 배포하는 파이프라인이고,
   통합 앱에 넣으면 다른 제품의 스코프를 바꿀 때마다(새 버전 Release + 재설치) **테마 배포가 흔들린다.**

`Nanugi Theme Push` 앱은 지금 그대로 둔다.

### StoreForge 가 스코프를 요구하지 않는 이유

축①의 주입 대상은 **shop 소유 메타필드**(`shop.metafields.storeforge.brand`)다.
`metafieldsSet` 은 "소유 리소스를 수정할 권한과 동일한 권한"을 요구하는데 **Shopify 에는 Shop 객체용
스코프가 존재하지 않는다** → 샵 메타필드는 스코프 없이 쓸 수 있다.

`write_metafields` 는 **폐지된 이름**이다. Dev Dashboard 에 입력하면 "Contains invalid scopes" 로
거부당한다. 이걸 필수 스코프로 걸어 뒀다가 주입이 영구히 409 로 막힌 적이 있다 — 되풀이하지 말 것.

---

## 2. 배포 방식과 그 대가

**Custom distribution** 을 쓴다 (승인 불요, 즉시 착수 — 기획안 §6.2 Phase 1).

그 대가로: **Custom 앱은 스토어 한 곳에만 설치할 수 있다.**
(예외는 같은 Plus 조직에 속한 스토어들, 그리고 transfer-disabled 개발 스토어뿐이다.)

> ### → **클라이언트 스토어마다 앱을 하나씩 만들어야 한다.**

여러 머천트 스토어에 앱 하나를 설치하려면 **Public distribution** 이어야 하고, 그건
**앱스토어에 등재하지 않더라도 Shopify 심사를 거친다.**

이 구조는 코드에 이미 반영돼 있다 — `Store` 행마다 `encrypted_client_id` / `encrypted_client_secret`
을 따로 갖는다. **스토어 N개 = 앱 N개 = 자격증명 N쌍.**

### 나중에 Public 으로 전환할 때

앱은 하나가 되고 스토어별 OAuth 액세스 토큰만 남는다. `Store.auth_type` 에 이미 `token` 방식이
있으므로 **데이터 모델을 바꾸지 않아도 된다.** 지금 Custom 으로 가도 퇴로는 열려 있다.

---

## 3. 클라이언트 스토어 온보딩 절차

새 클라이언트 스토어를 붙일 때마다 반복한다. 5~10분이면 끝난다.

### 3.1 Dev Dashboard 에서 앱 만들기

레거시 커스텀 앱(admin → 앱 개발)은 **2026-01-01 부터 신규 생성이 불가능하다.**
[dev.shopify.com/dashboard](https://dev.shopify.com/dashboard/) 에서 만든다.

```
1. Apps → Create app → Start from Dev Dashboard
   이름: "DWSTUDIO Suite — {클라이언트명}"   (스토어마다 하나이므로 이름에 스토어를 박는다)

2. Versions → Create version → Configuration → Admin API integration
   Access scopes:
     ✅ write_products    (ListPilot — 상품·변형·컬렉션 등록)
     ✅ read_products
     ✅ write_inventory   (ListPilot — 재고)
     ✅ read_inventory
     ✅ read_discounts    (Pricewave — 활성 할인 조회)
   ⚠️ write_metafields 는 없는 스코프다. 넣으면 거부당한다.
   ⚠️ write_themes 는 넣지 않는다 (보호 스코프. ThemePush 는 별도 앱).
   ⚠️ StoreForge(축①)만 쓸 거라면 스코프 없이도 동작한다. 하지만 나중에 다른 모듈을 켤 때
      재설치를 면하려면 처음부터 위 집합을 다 넣어 두는 편이 낫다.

3. Release  ← 릴리즈해야 스코프가 실제로 적용된다

4. Distribution → Choose distribution → Custom distribution
   → 스토어 도메인 입력 → Install link 생성
   (한 번 고르면 되돌릴 수 없다)

5. 설치: Install link 를 복사해, 그 스토어 관리자로 로그인된 브라우저에서 연다.
   파트너 계정으로 로그인된 창에서 열면 안 된다 — 시크릿 창을 쓴다.
   설치 후 App URL(플레이스홀더)로 리다이렉트되는데 정상이다. client_credentials 방식이라
   OAuth 리다이렉트도 임베드 화면도 쓰지 않는다.

6. Settings → Client credentials → Client ID / Client secret(Reveal) 복사
```

앱 스코프를 나중에 바꾸려면 **새 버전 Release + 앱 재설치**가 필요하다.
그래서 처음부터 세 모듈의 스코프 합집합(`INSTALL_SCOPES`)을 넣어 두는 편이 낫다 —
쓰지 않는 모듈이 있어도 나중에 켤 때 재설치를 면한다.

### 3.2 StoreForge 에 등록

관리자 페이지 → **스토어 → + 스토어 연동**

- 인증 방식: **client_credentials** (`shpat_…` 영구 토큰은 필요 없다)
- Client ID / Client secret 입력 → 저장하면 연결 테스트가 자동으로 돈다
- 스토어 상세 → **모듈** 에서 이 스토어에서 쓸 제품을 켠다

모듈을 켰는데 스코프가 모자라면 화면에 **"스코프 부족"** 으로 표시된다. 막지 않고 보여준다 —
켜지도 못한 채 이유를 짐작하게 만드는 것보다 낫다.

---

## 4. 코드에서의 위치

| | |
|---|---|
| 모듈 레지스트리 | `storeforge/api/app/capabilities.py` — **여기가 단일 진실 공급원** |
| 스토어별 켠 모듈 | `Store.enabled_modules` (콤마 구분) |
| 스코프 검사 | `Store.missing_scopes` — **켠 모듈의 필수 스코프에 대해서만** 검사한다 |
| API | `GET /stores/modules` (카탈로그) · `PUT /stores/{id}/modules` (토글) |
| 샵 메타필드 | `ShopifyClient.set/get/delete_shop_metafield` — 축①과 Pricewave 가 함께 쓴다 |

새 제품을 붙일 때는 `capabilities.MODULES` 에 항목을 추가하면 스코프 검사·화면·문서 기준이 함께 따라온다.

---

## 5. 이식 현황 (원본 저장소 → 통합 앱)

### Pricewave — 이식 완료

| 원본 (`dasomweb/pricewave`, Remix/TS) | 통합 앱 |
|---|---|
| `app/discount-sync.server.ts` (할인 파싱·선택) | `api/app/engine/pricewave.py` (순수 로직) |
| 〃 (GraphQL 왕복) | `ShopifyClient.active_discounts` / `set_shop_metafield` |
| `app/scheduler.server.ts` (5분 주기) | `main.py` 의 `_pricewave_loop` (`STOREFORGE_PRICEWAVE_SYNC_SECONDS`, 기본 300) |
| `extensions/pricewave-sale-price/` (Theme App Extension) | **`blocks/pricewave-sale-price.liquid`** (테마 블록) |
| Remix 임베드 UI · Prisma · OAuth 세션 | **버림** — 통합 앱의 스토어별 자격증명·관리자 페이지를 쓴다 |

**Theme App Extension 을 테마 블록으로 바꾼 이유**: 우리가 테마를 소유하고 있다.
확장을 쓰면 앱에 extension 을 붙이고 배포 파이프라인을 따로 둬야 하는데, 테마 블록으로 넣으면
기존 GitHub Actions 테마 배포에 그대로 얹힌다. 머천트는 테마 에디터에서 드래그해 쓴다.

메타필드 형식(`shop.metafields.pricewave.active_discount`)은 원본과 **똑같이 유지**했다 —
`type` / `value` / `code` / `startsAt` / `endsAt`. 블록과 서버가 이 형식으로 맞물린다.

### ListPilot — 이식 완료

| 원본 (`dasomweb/DW-ListPilot`, FastAPI) | 통합 앱 |
|---|---|
| `services/gemini.py` (상품 추출·설명) | `engine/listpilot/gemini.py` — **프롬프트 그대로** |
| `services/tag_engine.py` | `engine/listpilot/tags.py` (순수 로직) |
| `services/product_type.py` 의 프리셋 | `engine/listpilot/presets.py` |
| `services/excel_parser.py` · `pdf_parser.py` · `image_pipeline.process_image` | `engine/listpilot/parsers.py` |
| `services/shopify_client.push_to_shopify` (REST) | **`ShopifyClient.product_set`** (GraphQL) |
| `services/r2_client.py` (Cloudflare R2) | **`ShopifyClient.stage_upload`** (staged upload) |
| 자체 Store · `shopify_oauth.py` · `encryption.py` | **버림** — 통합 앱 것을 쓴다 |
| Next.js 프론트 | `web/app/stores/[id]/listpilot/` (업로드 → 검수 → 등록) |

**세 가지를 의도적으로 바꿨다.**

1. **REST → GraphQL `productSet`.** 원본은 `/admin/api/../products.json` 으로 상품을 올렸는데,
   상품 REST API 는 폐기 경로다 (공개앱 2025-02 / 커스텀앱 2025-04 마감, 100변형 초과 시 즉시 불가).
   기획안 §축② 도 `productSet` 을 지시하고 있었다 — **그대로 옮겼다면 죽은 코드를 이식하는 셈이었다.**
2. **R2 → Shopify staged upload.** 이미지의 종착지는 어차피 Shopify 다. 중간에 우리 버킷을 두면
   공개 URL·수명주기·삭제 정합성을 우리가 떠안는다. 인프라 의존이 하나 줄었다.
3. **LLM 은 Gemini 유지.** 축①은 Claude 지만, 도매 인보이스에서 여러 상품을 뽑아내는 이 프롬프트는
   실전 검증된 자산이라 모델을 갈아끼우면 회귀 위험이 크다. `STOREFORGE_GEMINI_API_KEY` 가 필요하며,
   없으면 **ListPilot 추출만 503** 이고 다른 모듈은 정상 동작한다.

**추출은 자동, 등록은 수동이다.** AI 가 뽑은 상품을 곧바로 스토어에 밀어 넣지 않는다. 등록도
`DRAFT` 상태로 올라간다 — 잘못 뽑힌 상품이 라이브로 뜨는 것보다 사람이 한 번 보는 편이 낫다.

가져오지 않은 것: 바코드 카메라 조회, Gemini 이미지 검색(grounding), 태그 사용 이력.
쓰는 곳이 생기면 그때 붙인다.
