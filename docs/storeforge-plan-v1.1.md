# AI 기반 Shopify 스토어 온보딩 자동화 시스템 기획안

**프로젝트 코드명**: StoreForge (가칭)
**작성일**: 2026-07-13
**작성**: DASOMWEB LLC
**문서 버전**: v1.1 (실제 코드 조사 반영 / 내부 검토용)

> v1.0 대비 변경 요약
> - 베이스 테마를 **자사 나누기(nanugi) 테마**로 확정 (Dawn 계열 지원 → 폐기)
> - LLM 역할을 **"315개 값 생성" → "브랜드 3~5색 선택"** 으로 축소, 파생 엔진 신설
> - 폰트/컬러 주입을 **metafield 경로**로 전환 → `write_themes` 보호 스코프 의존 제거
> - **GitHub 연동 역류 리스크** 신규 식별 및 대응 명시
> - 로드맵에 **0주차(테마 개조)** 신설, 축① / 축② 순서 교체

---

## 1. 개요

### 1.1 한 줄 정의

셀러가 브랜드 정보와 상품 원본 데이터만 입력하면, AI가 **자사 나누기 테마**의 디자인 세팅과 상품/컬렉션 구축을 대리 수행하여 초기 스토어 셋업을 5분 내로 완료하는 자동화 시스템.

### 1.2 핵심 원칙 (v1.0에서 유지)

Shopify 엔진과 경쟁하지 않고, 소스코드를 자체 인프라에서 관리하지 않는다. Shopify 공식 Admin GraphQL API 규격에 따라 데이터를 주입하는 **단방향 경량 중계 서버(Lightweight Relay)** 아키텍처를 채택한다.

### 1.3 v1.1에서 추가된 핵심 원칙 — "우리가 소유한 테마만 세팅한다"

v1.0은 "Dawn 계열 무료 테마 지원"을 전제했다. **이는 폐기한다.**

DASOMWEB은 이미 완성된 자사 테마(나누기, Horizon/Tinker 계열, v1.0.84)를 보유하고 있다. 남의 테마 스키마에 맞추려 애쓰는 대신 **우리가 스키마를 소유한 테마 1종에만 주입**하면, v1.0이 리스크로 꼽았던 "테마별 스키마 편차"가 리스크가 아니라 **존재하지 않는 문제**가 된다.

| | v1.0 (Dawn 계열 지원) | v1.1 (자사 테마 전용) |
|---|---|---|
| 스키마 편차 | 테마마다 다름 → 검증 레이어로 흡수 | **없음** (우리가 정의) |
| LLM 매핑 난이도 | 미지의 스키마 추론 | 고정 스키마, 슬롯 채우기 |
| 테마 업데이트 대응 | 남이 바꾸면 파손 | 우리가 통제 |
| 사업 모델 | 앱 단독 | **테마 + 앱 번들** (락인 ↑) |

### 1.4 스코프 확정 (v1.0에서 유지)

테마 세팅은 **"최초 온보딩 1회성 주입"** 으로 고정한다. 세팅 완료 후 머천트가 어드민에서 수동 수정한 값에 대해 재동기화·재주입하지 않는다. "AI 재세팅"은 v1에서 명시적으로 제외한다.

---

## 2. 베이스 테마 실사 결과 (신규)

기획 확정을 위해 나누기 테마 코드를 실제 조사한 결과다. 이 절의 사실들이 아래 모든 설계 결정의 근거다.

### 2.1 테마 정체

```
theme_name    : nanugi
theme_version : 1.0.84
theme_author  : DASOMWEB
아키텍처       : Horizon/Tinker 계열 (Dawn 아님)
구성          : sections 44 / blocks 96(_ prefix) / snippets 112 / templates 13
```

`sections/section.liquid` + `blocks/_*.liquid` 중첩 구조의 **theme blocks 아키텍처**다. Dawn과는 세대가 다르며, **Dawn용 프롬프트·검증기는 한 줄도 재사용되지 않는다.**

### 2.2 컬러 시스템 — 315개 값

```
config/settings_data.json
  └ color_schemes
      ├ scheme-1 … scheme-8, scheme-3f8267df-…   (9개)
      └ 스킴당 키 35개
          background, foreground, foreground_heading, primary, primary_hover,
          border, shadow,
          primary_button_{background,text,border,hover_background,hover_text,hover_border},
          secondary_button_{...×6},
          input_{background,text_color,border_color,hover_background},
          variant_{...×6}, selected_variant_{...×6}

  총 9 × 35 = 315개 컬러 값
```

**LLM에게 315개를 생성시키는 접근은 성립하지 않는다.** v1.0의 "LLM이 스키마 구조에 맞춰 설정 객체를 생성한다"는 이 테마에서 반드시 파손된다. → §4.2 파생 엔진으로 해결.

### 2.3 CSS 변수 생성 지점 — 단일 병목 (기회)

`snippets/color-schemes.liquid`가 `settings.color_schemes`를 순회하며 `--color-*` CSS 커스텀 프로퍼티를 전부 뿜는다. `layout/theme.liquid:37`에서 **단 한 번** 렌더된다.

```liquid
layout/theme.liquid
  36: {%- render 'theme-styles-variables' -%}   ← 폰트 @font-face + 타이포 변수
  37: {%- render 'color-schemes' -%}            ← --color-* 315개
  38: ★ 여기에 brand-overrides 삽입 지점
```

**이 뒤에 override 스니펫 하나만 끼우면 테마 전체 색이 바뀐다.** CSS 캐스케이드상 나중 선언이 이긴다. `settings_data.json`을 건드릴 필요가 없다.

### 2.4 폰트 — metafield 우회 불가 (제약)

`snippets/theme-styles-variables.liquid`(692줄)는 다음을 사용한다:

```liquid
assign primary_font = settings.type_body_font        ← font_picker가 반환하는 폰트 객체
echo primary_font | font_face: font_display: 'swap'  ← 객체를 요구하는 필터
assign x = primary_font | font_modify: 'weight', 'bold'
```

**metafield 문자열("oswald_n4")을 Shopify 폰트 객체로 변환하는 Liquid 필터는 존재하지 않는다.** 따라서 폰트는 컬러처럼 metafield override로 처리할 수 없다. → §4.3 번들 폰트로 해결.

현재 값: body=`roboto_n4`, heading=`bebas_neue_n4`, subheading=`oswald_n4`, accent=`bebas_neue_n4`

### 2.5 템플릿 구조 — 프리셋 부담이 작다

```
index.json            4 sections  [hero, section, product-list, section]   ← 유일하게 복잡
product.json          2  [product-information, product-recommendations]
collection.json       2  [section, main-collection]
cart / 404 / search   2 each
article/blog/page/…   1 each
```

**홈을 제외한 12개 템플릿은 1~2섹션으로 단순하다.** 프리셋화 대상은 사실상 `index.json` 하나다. 섹션 preset은 이미 30개 정의되어 있어 재료도 갖춰져 있다.

### 2.6 GitHub 연동 역류 (신규 리스크)

현재 라이브 테마 `159722602713`은 **GitHub 연동 상태**다(그래서 "Update from Shopify" 커밋이 자동 생성된다). 이 테마에 API로 파일을 주입하면 **GitHub로 역류하여 커밋이 생기고 다음 배포와 충돌한다.**

v1.0이 "구조적으로 제거했다"고 선언한 동기화 문제가, 이 저장소에서는 여전히 살아있다. → §6.3 대응.

### 2.7 부수 사실

- `settings_data.json` / `index.json`에 `/* */` **주석이 포함**되어 있어 표준 JSON 파서로 로드되지 않는다. 파이프라인은 comment-tolerant 파서(JSON5 계열) 전제.
- `settings_data.json`의 `current`에 `content_for_index` 키가 존재한다. 홈 구성이 템플릿 파일에만 있지 않다.
- 현재 테마 전체에 `shop.metafields` 사용 사례는 **0건**. metafield 도입은 신규 설계다.

---

## 3. 배경 및 시장 문제 정의 (v1.0 유지)

### 3.1 셀러의 Pain Point

신규 Shopify 셀러(도매→온라인 전환 B2B, 한인 커머스 사업자)의 최대 진입 장벽은 결제나 물류가 아니라 **초기 구축 노동**이다: 테마 디자인 세팅(수 시간~수일), 상품 등록(가장 반복적), 컬렉션 구성.

### 3.2 DASOMWEB의 전략적 위치

- **상품 등록 자동화는 ListPilot으로 검증 완료.** 축②는 ListPilot의 직접 확장이다.
- **자사 테마 보유.** 이것이 v1.1의 최대 자산이다(§1.3).
- **에이전시로서 즉시 적용 가능한 실전 테스트베드 보유.** 커스텀 앱 형태로 외부 승인 없이 오늘부터 구현·검증 가능.

### 3.3 경쟁 지형 (신규 — 솔직한 평가)

Shopify 자체가 Horizon 테마 + Sidekick으로 "AI 스토어 셋업"을 밀고 있다. **축①(AI가 컬러/폰트를 고름) 단독으로는 차별화되지 않는다.**

진짜 해자는 **축②**다 — 한국 B2B 도매 셀러의 원본 데이터(도매 사이트 URL, 잡다한 이미지, 메모)를 완성된 상품 카탈로그로 바꾸는 파이프라인. 이건 Shopify가 하지 않고, 한인 커머스 컨텍스트를 아는 우리만 한다.

→ **로드맵에서 축②를 앞으로 당긴다**(§7). 축①은 획득 훅, 축②는 리텐션 축이자 해자.

---

## 4. 제품 정의: 2축 구조

### 축 ① — 테마 디자인 자동 세팅 (Theme Configurator)

#### 4.1 흐름

```
브랜드 자연어 입력
   ↓
[LLM] 브랜드 해석 → 프리셋 선택 + 브랜드 색 3~5개 + 카피 슬롯   ← LLM은 여기까지만
   ↓
[파생 엔진] 3~5색 → 315개 컬러 값 전개 + WCAG 대비 검증/보정    ← 결정론적 코드
   ↓
[검증] Pydantic 스키마 검증
   ↓
[주입] shop metafield (+ 프리셋 템플릿)
   ↓
나누기 테마가 metafield를 읽어 CSS 변수 override
```

#### 4.2 LLM 역할 축소 + 파생 엔진 (v1.1 핵심 설계)

LLM은 **"고르기"** 만 하고, **"채우기"** 는 코드가 한다.

**LLM 출력 (전부):**
```json
{
  "preset": "minimal-fashion",
  "colors": {
    "primary":    "#1a1a1a",
    "background": "#faf8f5",
    "foreground": "#1a1a1a",
    "accent":     "#c3cca6"
  },
  "fonts": { "heading": "bebas_neue", "body": "roboto" },
  "copy": { "hero_title": "…", "hero_subtitle": "…" }
}
```

**파생 엔진 (Python, LLM 아님):**
```
primary                        → primary_button_background
primary  · 명도 -12%           → primary_button_hover_background
foreground · alpha 8%          → input_border_color / border
background · 명도 ±(스킴 반전)  → scheme-2 … scheme-8 자동 생성
…
9 스킴 × 35 키 = 315개 값 결정론적 전개
   ↓
WCAG AA 대비비 검증 → 미달 시 자동 보정 (LLM 재호출 없음)
```

이 구조의 효과:
- LLM 출력 표면적이 315개 → **10개 미만**으로 축소 → 파손 확률 급감
- 대비비/일관성이 **코드로 보장**됨 → 성공지표 "무수정 채택률 70%"가 현실적 목표가 됨
- 재생성 루프가 거의 발동하지 않음 → 비용·지연 감소

#### 4.3 주입 방식 — metafield 경로 (v1.1 핵심 결정)

**결정: 번들 폰트 + metafield.** `write_themes` 보호 스코프 의존을 제거한다.

| 항목 | 주입 방식 | 필요 스코프 |
|---|---|---|
| 컬러 315값 | `shop.metafields.storeforge.brand` → `--color-*` override | `write_metafields` (**비보호**) |
| 라운드/페이지폭 | 동일 | `write_metafields` |
| 폰트 | OFL 폰트 6~8종을 `assets/*.woff2`로 **번들**, metafield로 선택 → `@font-face` | `write_metafields` |
| 카피/이미지 | 섹션 Liquid에 metafield fallback 심음 | `write_metafields` |

**신규 파일: `snippets/brand-overrides.liquid`** — `theme.liquid:38`(color-schemes 직후)에 삽입.

```liquid
{%- assign b = shop.metafields.storeforge.brand.value -%}
{%- if b -%}
{% style %}
  :root, .color-scheme-1 { --color-primary: {{ b.primary }}; … }
  @font-face { font-family: '{{ b.heading_font }}'; src: url({{ b.heading_font | append: '.woff2' | asset_url }}); }
{% endstyle %}
{%- endif -%}
```

**대가:** 폰트 선택지가 우리가 큐레이션한 세트로 제한된다. 한글 폰트(Pretendard, 나눔스퀘어 등)를 포함할 수 있으므로 **한인 B2B 타겟에는 오히려 유리**하다.

**이득:** Phase 3 퍼블릭 SaaS에서 **exemption 승인이 아예 불필요**해진다(§6).

#### 4.4 홈 레이아웃 프리셋

**결정: 현 `index.json` 파생.** 지금 나누기 홈(`hero + section + product-list + section`)을 기준으로 섹션 조합·순서만 바꾼 변형 5~8종을 **손으로 만들어 눈으로 검증**한다.

```
presets/
  ├ minimal-fashion.json
  ├ bold-b2b.json
  ├ image-first.json
  └ … 5~8종
```

LLM은 랜덤 섹션 ID(`hero_6ATUTw`)나 중첩 blocks 구조를 **생성하지 않는다.** 프리셋 이름 하나를 고를 뿐이다.

#### 4.5 미결 쟁점 — 프리셋 주입 경로 (중요)

컬러·폰트는 metafield로 탈출했으나, **홈 레이아웃 프리셋은 `templates/index.json` 교체를 의미하므로 마지막 `write_themes` 잔존 지점**이다. 두 가지 해법이 있다.

**(a) 테마 파일 주입** — `themeFilesUpsert`로 `index.json` 교체
- 장점: 구현 단순, 머천트가 이후 테마 에디터로 자유롭게 재편집 가능
- 단점: `write_themes` 필요 → Phase 3에서 exemption 병목 부활

**(b) 테마 내장 + metafield 스위치** — 프리셋을 Liquid 안에 넣고 `shop.metafields.storeforge.layout` 값으로 분기
- 장점: `write_themes` **완전 탈출**. 온보딩 전체가 metafield 쓰기만으로 완결
- 단점: 홈이 사실상 단일 섹션이 되어 **테마 에디터의 드래그 재배치 UX가 약화**됨

**권고:** Phase 1(커스텀 앱)은 제약이 없으므로 **(a)로 빠르게 출시**하되, 0주차 테마 개조 시 섹션 카피에 metafield fallback을 미리 심어 **(b)로 전환 가능한 상태**를 만들어 둔다. Phase 3 진입 직전에 (b)로 스위치한다.

#### 4.6 v1 지원 범위

**나누기 테마 전용.** 타 테마는 명시적으로 거부(graceful fail)한다. 이는 제약이 아니라 §1.3의 전략적 선택이다.

---

### 축 ② — 상품/컬렉션 자동 구축 (ListPilot 확장) — v1.0 유지

- **입력**: 도매 사이트 URL, 이미지, 간단 메모 등 상품 원본 데이터
- **생성**: AI가 SEO 표준 상품명, 상세설명(HTML), 태그, 가격, 옵션(Variant) 생성. ListPilot 기존 파이프라인(Gemini 처리, 제조사 이미지 검색, 멀티소스 이미지) 재사용
- **등록**:
  - 상품+옵션: `productSet` (2024-04 이후 `productCreate`는 variant 직접 생성 불가)
  - 대량: `productVariantsBulkCreate` / Bulk Operations
  - 이미지: staged upload → `fileCreate`
- **컬렉션**: AI 분류 결과에 따라 Collection API로 자동 생성·정렬

---

## 5. 시스템 아키텍처

```
[사용자 (웹 대시보드)]
        │  브랜드 정보 / 상품 원본 데이터
        ▼
[Front-end: Next.js 14 — Vercel]
        │
        ▼
[API Server: FastAPI — Railway]
        │
        ├─→ [LLM] 브랜드 해석 → 프리셋 + 3~5색 + 카피        (축①, 출력 10개 미만)
        ├─→ [파생 엔진 (Python)] 3~5색 → 315값 + WCAG 검증    (축①, LLM 아님)
        ├─→ [Gemini 파이프라인] 상품 텍스트 생성              (축②, ListPilot 재사용)
        │
        ├─→ [Cloudflare R2]  이미지 스테이징
        │
        ▼
[Shopify Admin GraphQL API]
   ├─ metafieldsSet                  (축①  ← 주 경로, write_metafields)
   ├─ themeFilesUpsert               (축①  ← 프리셋 한정, §4.5 미결)
   ├─ productSet / Bulk Operations   (축②)
   └─ Collection API                 (축②)
        │
        ▼
[나누기 테마] snippets/brand-overrides.liquid 가 metafield를 읽어 CSS 변수 override
```

**스택**: ListPilot과 동일(Next.js 14 / FastAPI / Railway / Vercel / R2). 코드·인프라·운영 노하우 전면 재사용. 서버는 무상태 중계이므로 1인 운영 가능.

**AI 엔진 분리**: 축①(브랜드 해석 → 구조화 출력)과 축②(상품 텍스트 생성)를 별도 모델로 운용하여 비용/품질을 독립 최적화. 축①은 출력이 10개 미만으로 작아져 v1.0 대비 **대형 컨텍스트 모델이 불필요**해졌다(비용 절감).

**GraphQL 운영**: cost 기반 rate limit. 대량 상품 등록은 Bulk Operations로 우회. 테마 파일 주입 시 job 완료 폴링을 표준 플로우에 포함.

---

## 6. 배포 전략

### 6.1 보호 스코프 재평가 (v1.1에서 변경)

v1.0은 `write_themes`(Online Store 보호 스코프) 승인을 Phase 3의 필수 관문으로 봤다. **§4.3 metafield 경로 채택으로 이 의존이 제거된다.**

| 경로 | 필요 스코프 | 보호 여부 | Phase 3 exemption |
|---|---|---|---|
| metafield (컬러·폰트·카피) | `write_metafields` | 비보호 | **불필요** |
| 상품·컬렉션 (축②) | `write_products` | 비보호 | **불필요** |
| 프리셋 (§4.5-a 선택 시) | `write_themes` | 보호 | 필요 → (b)로 전환 시 소멸 |

### 6.2 3단계 배포

**Phase 1 — 커스텀 앱 (즉시 착수, 승인 불요)**
스토어별 커스텀 앱 설치. 보호 스코프 제약 없이 전 기능 사용. DASOMWEB 클라이언트 구축 프로젝트의 내부 무기로 투입하여 구축 납기·원가를 단축한다. 이 단계에서 시스템이 곧바로 매출(구축 용역 마진)에 기여한다.

**Phase 2 — 실적 축적 + (b) 전환**
Phase 1 실적을 쌓으면서 §4.5(b) 전환을 완료해 `write_themes` 의존을 소멸시킨다. **exemption 신청 자체가 불필요해지는 것이 목표다.** (전환 실패 시 백업으로 exemption 신청 — v1.0의 원안이 리스크 헤지로 남는다.)

**Phase 3 — 퍼블릭 SaaS**
"나누기 테마 + StoreForge 앱" 번들로 App Store 등재. 셀프서브 구독. **보호 스코프 관문이 없으므로 승인 지연 리스크가 구조적으로 제거된다.**

### 6.3 GitHub 연동 역류 대응 (§2.6)

주입 대상 테마는 **반드시 GitHub 미연동 테마**여야 한다.

```
[소스 테마]  이 저장소 (GitHub 연동, 개발용)
      │  빌드 → 테마 zip → R2
      ▼
[고객 스토어 테마]  themeCreate(source: zipUrl) 로 생성, GitHub 미연동
      │
      ▼  metafieldsSet 주입 (역류 없음)
    발행
```

라이브 테마(`159722602713`)에 직접 주입하는 일은 **어떤 경우에도 없어야 한다.**

---

## 7. 개발 로드맵 (MVP 9주 — 0주차 신설, 축①/축② 순서 교체)

| 주차 | 마일스톤 | 내용 |
|---|---|---|
| **0** | **테마 개조 (신규)** | `snippets/brand-overrides.liquid` 신설 + `theme.liquid:38` 삽입 / OFL·한글 폰트 6~8종 woff2 번들 / 홈 프리셋 5~8종 손으로 제작·검증 / 섹션 카피 metafield fallback 심기 |
| 1–2 | 기반 구축 | 커스텀 앱 OAuth, FastAPI 중계 서버, `metafieldsSet` + `themeCreate` E2E (더미 값으로 **주입 파이프라인부터** 관통) |
| **3–4** | **축 ② 먼저** | ListPilot 파이프라인 이식, `productSet` / Bulk Operations 전환, 컬렉션 자동 분류 — **해자부터 확보** |
| 5–6 | 축 ① 코어 | 브랜드 해석 LLM(프리셋+3~5색), **파생 엔진**(315값 전개 + WCAG 보정), Pydantic 검증 |
| 7 | 대시보드 | Next.js 온보딩 위저드 (브랜드 입력 → 미리보기 → 실행) |
| 8 | 실전 검증 | 자사/파트너 스토어 2곳 이상 실제 온보딩, 소요 시간·수정률 측정 |

v1.0 대비: 0주차 신설(+1주), 축② 우선(3–4주차), 축① 후행(5–6주차).

---

## 8. 리스크 및 대응

| 리스크 | 영향 | 대응 | 상태 |
|---|---|---|---|
| ~~퍼블릭 앱 exemption 미승인~~ | ~~축① SaaS 확장 지연~~ | **metafield 경로로 의존 제거** (§4.3, §6.1) | **v1.1에서 해소** |
| ~~테마별 스키마 편차~~ | ~~지원 범위 한계~~ | **자사 테마 전용으로 스코프 확정** (§1.3) | **v1.1에서 해소** |
| **LLM이 315개 값을 못 맞춤** | 테마 설정 깨짐 | **LLM 출력을 3~5색으로 축소 + 결정론적 파생 엔진** (§4.2) | v1.1 신규 대응 |
| **폰트 metafield 우회 불가** | 브랜드 폰트 제약 | **OFL·한글 폰트 번들** (§4.3). 선택지 제한을 수용 | v1.1 신규 식별 |
| **GitHub 연동 역류** | 배포 충돌, 히스토리 오염 | **주입 대상은 GitHub 미연동 테마만** (§6.3) | v1.1 신규 식별 |
| **JSON 주석 파싱 실패** | 파이프라인 D1 파손 | comment-tolerant 파서 전제 (§2.7) | v1.1 신규 식별 |
| 프리셋 주입에 `write_themes` 잔존 | Phase 3 병목 | Phase 1은 (a), Phase 2에 (b) 전환 (§4.5) | **미결 — 결정 필요** |
| 머천트 수동 수정과의 충돌 | 신뢰 훼손 | 온보딩 1회성 스코프 고정, 재주입 v1 제외 (§1.4) | v1.0 유지 |
| Shopify 자체 AI 셋업과 경쟁 | 축① 차별화 실패 | **축②(한국 B2B 도매 데이터)를 해자로 전면 배치** (§3.3) | v1.1 신규 식별 |
| API 버전 변경 (분기별) | 파이프라인 파손 | GraphQL 버전 고정 + 분기별 changelog 점검 | v1.0 유지 |
| rate limit | 대량 등록 지연 | Bulk Operations 표준화, job 큐잉 | v1.0 유지 |

**v1.0의 최대 리스크 두 개(exemption 승인, 테마 편차)가 v1.1 설계로 소멸했다.** 대신 실제 코드에서 발견된 구체적 리스크 네 개가 새로 들어왔고, 모두 대응책이 있다.

---

## 9. 비즈니스 모델

**단계 1 (Phase 1 병행)** — **구축 패키지 상품화.** "나누기 테마 셋업 + 상품 N개 등록"을 정찰제 패키지로 판매. AI 자동화로 원가를 낮춰 수작업 에이전시 대비 가격·납기 우위 확보. 기존 한인 B2B 클라이언트 채널에 즉시 적용.

**단계 2 (Phase 3 이후)** — **테마 + SaaS 번들 구독.** 나누기 테마와 StoreForge 앱을 묶어 셀프서브 온보딩 + 상품 등록 크레딧 과금. 테마를 함께 파는 구조라 **락인이 앱 단독보다 강하다**(v1.0 대비 개선).

**소구 메시지**: "가장 귀찮은 초기 구축과 상품 등록, AI가 5분 만에 끝냅니다."

---

## 10. 성공 지표 (MVP)

| 지표 | 목표 | v1.1 근거 |
|---|---|---|
| 스토어 1곳 온보딩 총 소요 시간 | 수작업 대비 90%↓ (입력 후 5분 내) | — |
| AI 생성 테마 설정 무수정 채택률 | **70% 이상** | 파생 엔진이 대비비·일관성을 코드로 보장하므로 **달성 가능한 수치**. v1.0의 자유 생성 방식이었다면 도달 불가능했다 |
| 상품 등록 필드 오류율 | 3% 미만 | ListPilot 기존 지표 승계 |
| Phase 1 내 실제 클라이언트 적용 | 3건 이상 | — |

---

## 11. 결론

v1.0의 판단 중 **1회성 주입 스코프 고정 · 커스텀 앱 우선 · ListPilot 스택 재사용**은 전부 옳았고 유지한다.

v1.1은 여기에 실제 코드 조사 결과를 반영해 세 가지를 바꿨다.

1. **베이스 테마를 자사 나누기 테마로 확정** → "테마별 스키마 편차" 리스크 소멸, 테마+앱 번들이라는 더 강한 사업 구조 확보
2. **LLM을 315개 값 생성기가 아니라 3~5색 선택기로 축소**, 나머지는 결정론적 파생 엔진 → 품질·비용·안정성 동시 개선
3. **주입 경로를 metafield로 전환** → v1.0이 유일한 외부 관문으로 꼽았던 `write_themes` exemption 의존을 **구조적으로 제거**

남은 결정은 **§4.5(프리셋 주입 경로 a/b)** 하나다. Phase 1은 (a)로 진행 가능하므로 **착수를 막지 않는다.**

**즉시 착수를 권고한다. 시작점은 0주차 테마 개조다.**
