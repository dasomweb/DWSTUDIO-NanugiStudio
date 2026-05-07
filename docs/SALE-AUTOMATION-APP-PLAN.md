# Sale Automation App — 개발 계획서

DWSTUDIO 자체 클라이언트용 Shopify Sale 자동화 앱.
스케줄 기반 할인, 컬렉션/태그 일괄 적용, sale 배지 자동 표시를 제공합니다.

---

## 1. 프로젝트 개요

| 항목 | 내용 |
|------|------|
| **앱 이름** | DWSTUDIO Sale Manager (가칭) |
| **배포 방식** | Custom Distribution (DWSTUDIO 클라이언트 스토어들에만 설치) |
| **첫 타겟 스토어** | nanugi.myshopify.com |
| **Tech Stack** | Remix + Node.js + Prisma |
| **DB** | PostgreSQL (Railway) |
| **호스팅** | Railway |
| **저장소** | 새 GitHub repo (예: `dasomweb/sale-automation-app`) — 이 테마 repo와 분리 |

---

## 2. 핵심 기능 (MVP)

### 2.1 스케줄 세일
- 시작/종료 일시 지정
- 종료 시 `compare_at_price` 자동 복구
- 실행 보장 (앱이 다운되어 있던 시간이 있어도 누락 없이 처리)

### 2.2 할인 적용
- **% 할인** (예: 20% off)
- **$ 할인** (예: $5 off)
- 적용 방식: 상품의 `price`를 할인가로 변경, 기존 `price`는 `compare_at_price`로 이동

### 2.3 일괄 대상 지정
- **Collection 기반**: 컬렉션 전체 상품
- **Tag 기반**: 특정 태그 가진 상품 (예: `summer-sale`)
- **개별 상품 선택**: 수동 다중 선택
- **전 상품**: 사이트 전체

### 2.4 Sale 배지 자동 표시
- 상품에 `custom.sale_badge` 메타필드 자동 입력 (예: `"-20%"`)
- 테마는 이 메타필드 읽어 PDP/PLP에 배지 표시
- 세일 종료 시 메타필드 자동 삭제

---

## 3. 시스템 아키텍처

```
┌─────────────────────┐       ┌──────────────────────────┐
│  Shopify Admin UI   │       │   클라이언트 스토어들       │
│  (App Bridge 임베드) │       │ nanugi.myshopify.com 등  │
└─────────┬───────────┘       └─────────┬────────────────┘
          │                             │
          │ Polaris UI                  │ Admin API
          │ (Remix routes)              │ (variants.update,
          ▼                             │  metafields.set)
┌─────────────────────────────────────────────────────────┐
│                    Sale Automation App                   │
│                  (Railway, Remix server)                 │
│                                                          │
│  ┌────────────┐  ┌─────────────┐  ┌─────────────────┐  │
│  │ OAuth 인증  │  │ Webhook 수신 │  │  Scheduler      │  │
│  │ (세션 저장) │  │ (앱 설치/제거)│  │ (cron 5min)    │  │
│  └────────────┘  └─────────────┘  └────────┬────────┘  │
│                                             │            │
│                                             ▼            │
│                              ┌─────────────────────┐    │
│                              │  Sale Executor      │    │
│                              │  (시작/종료 처리)     │    │
│                              └──────────┬──────────┘    │
│                                         │               │
└─────────────────────────────────────────┼───────────────┘
                                          │
                                          ▼
                              ┌──────────────────────┐
                              │   PostgreSQL         │
                              │   - Stores (세션)    │
                              │   - Sales (캠페인)   │
                              │   - SaleProducts    │
                              │   - SaleSnapshots   │ ← 원래 가격 백업
                              └──────────────────────┘
```

---

## 4. 데이터 모델

```prisma
// prisma/schema.prisma

model Store {
  id           String   @id @default(cuid())
  shop         String   @unique  // nanugi.myshopify.com
  accessToken  String
  scope        String
  installedAt  DateTime @default(now())
  uninstalledAt DateTime?

  sales        Sale[]
}

model Sale {
  id           String   @id @default(cuid())
  store        Store    @relation(fields: [storeId], references: [id])
  storeId      String

  name         String   // 캠페인 이름 (예: "Summer Sale 2026")
  status       SaleStatus  // SCHEDULED | ACTIVE | ENDED | CANCELLED

  startsAt     DateTime
  endsAt       DateTime

  discountType DiscountType  // PERCENTAGE | FIXED_AMOUNT
  discountValue Decimal       // 20 (% 또는 $)

  targetType   TargetType    // COLLECTION | TAG | PRODUCTS | ALL
  targetIds    String[]      // collection ID, tag, product IDs

  badgeText    String?       // "-20%" 등 (자동 생성 가능)

  createdAt    DateTime @default(now())
  updatedAt    DateTime @updatedAt

  snapshots    SaleSnapshot[]

  @@index([status, startsAt, endsAt])
}

model SaleSnapshot {
  // 세일 적용 전 원래 가격을 저장 — 종료 시 복구용
  id            String   @id @default(cuid())
  sale          Sale     @relation(fields: [saleId], references: [id])
  saleId        String

  productId     String   // Shopify product GID
  variantId     String   // Shopify variant GID
  originalPrice Decimal
  originalCompareAtPrice Decimal?

  appliedAt     DateTime @default(now())
  revertedAt    DateTime?

  @@index([saleId])
  @@index([variantId])
}

enum SaleStatus {
  SCHEDULED
  ACTIVE
  ENDED
  CANCELLED
}

enum DiscountType {
  PERCENTAGE
  FIXED_AMOUNT
}

enum TargetType {
  COLLECTION
  TAG
  PRODUCTS
  ALL
}
```

---

## 5. 핵심 플로우

### 5.1 세일 시작 (Scheduler가 매 5분마다 체크)
```
1. status = SCHEDULED && startsAt <= now() 인 Sale 조회
2. 각 Sale에 대해:
   a. 대상 상품/variant 목록 결정 (collection/tag/products 기반)
   b. 각 variant마다:
      - 현재 price, compare_at_price를 SaleSnapshot에 저장
      - 새 price = 할인가 계산
      - 새 compare_at_price = 원래 price
      - Admin API로 productVariantUpdate
      - 상품에 metafield: custom.sale_badge = "-20%" 설정
   c. Sale.status = ACTIVE
3. 트랜잭션으로 atomic 처리. 실패 시 롤백.
```

### 5.2 세일 종료
```
1. status = ACTIVE && endsAt <= now() 인 Sale 조회
2. SaleSnapshot 기반으로 원래 가격 복구:
   - price = originalPrice
   - compare_at_price = originalCompareAtPrice
3. metafield custom.sale_badge 삭제
4. Sale.status = ENDED, snapshot.revertedAt = now()
```

### 5.3 멱등성 보장
- Scheduler가 중복 실행되어도 안전하도록 락 사용 (`SELECT FOR UPDATE`)
- 이미 ACTIVE인 Sale은 다시 적용 안 함
- 이미 ENDED인 Sale은 다시 복구 안 함

---

## 6. 테마 측 통합

이 앱과 함께 동작하려면 클라이언트 테마(NANUGI 등)에 metafield 노출 코드 추가.

**상품 카드 (`blocks/_product-card.liquid` 등)**:
```liquid
{%- liquid
  assign sale_badge = product.metafields.custom.sale_badge
-%}
{%- if sale_badge != blank -%}
  <span class="sale-badge">{{ sale_badge }}</span>
{%- endif -%}
```

**상품 페이지 (`blocks/_product-details.liquid`)** — 동일하게.

→ NANUGI 테마에는 추후 별도 PR로 추가.

---

## 7. 개발 단계 (Phase)

### Phase 1: 기반 구축 (1주)
- [ ] Shopify Partner 계정 생성, 새 앱 등록
- [ ] Remix 프로젝트 초기화 (`npm init @shopify/app@latest`)
- [ ] Railway 프로젝트 생성, PostgreSQL 추가
- [ ] OAuth 인증 플로우 동작 확인
- [ ] DB 마이그레이션 (Prisma)
- [ ] 기본 임베드 UI (Polaris) 띄우기

### Phase 2: Sale CRUD (1주)
- [ ] Sale 생성 폼 (이름, 기간, 할인, 대상)
- [ ] Sale 목록/상세 페이지
- [ ] 대상 상품 목록 미리보기 (Admin API GraphQL)
- [ ] Sale 수정/취소

### Phase 3: 실행 엔진 (1.5주)
- [ ] Scheduler (cron 5min)
- [ ] Sale Executor: 시작 처리 (snapshot + 가격 변경 + 메타필드)
- [ ] Sale Executor: 종료 처리 (가격 복구 + 메타필드 삭제)
- [ ] 에러 처리, 재시도, 로깅
- [ ] 멱등성 검증

### Phase 4: 안정화 + 테마 통합 (0.5주)
- [ ] Webhook 수신 (app/uninstalled — 세일 정리)
- [ ] NANUGI 테마에 sale badge 표시 코드 추가
- [ ] 통합 테스트 (실제 nanugi 스토어로)

### Phase 5: 폴리싱 (0.5주)
- [ ] 에러 알림 (실패 시 이메일/slack)
- [ ] 분석 (적용 상품 수, 실행 시간)
- [ ] 문서

**총 예상: 4.5주 (1인 풀타임 기준)**

---

## 8. 비용

| 항목 | 비용 |
|------|------|
| Shopify Partner 계정 | 무료 |
| Railway (Hobby) | $5/월 (앱) + $5/월 (PostgreSQL) = **$10/월** |
| 도메인 (선택, 예: salemanager.dwstudio.cc) | $12/년 |
| **합계** | **약 $10~15/월** |

스토어 늘어나도 Railway 한 인스턴스에서 처리 가능 (수십 스토어까지). 트래픽 늘면 Railway 플랜 업그레이드 ($20/월~).

---

## 9. 고려사항 / 리스크

### 9.1 가격 충돌
- 클라이언트가 세일 진행 중에 수동으로 상품 가격 변경하면? → snapshot 정합성 깨짐
- **대응**: webhook `products/update` 수신 → 세일 진행 중인 상품이면 snapshot 갱신

### 9.2 다중 세일 중첩
- 같은 상품에 두 세일이 동시 적용되면? → 후자가 전자를 덮어씀
- **대응**: MVP에서는 "한 상품당 한 세일만 active" 제약. 추후 priority 기능 추가.

### 9.3 Shopify Rate Limit
- 1만 상품 일괄 변경 시 API 제한 (REST: 2 req/s, GraphQL: cost-based)
- **대응**: GraphQL Bulk Operations 활용, 배치 처리

### 9.4 시간대 (Timezone)
- 세일 시간을 클라이언트 로컬 시간으로 받되 DB는 UTC 저장
- 스토어 timezone은 Shopify Shop API에서 가져옴

### 9.5 환불/캐시
- compare_at_price는 즉시 반영되지만 CDN 캐시 때문에 일부 페이지에서 지연 가능
- **대응**: 클라이언트에 "최대 5분 지연" 안내

---

## 10. 다음 단계

1. **결정 사항 확인** — 이 계획서 검토 후 OK
2. **Shopify Partner 계정 생성** ([partners.shopify.com](https://partners.shopify.com))
3. **새 GitHub repo 생성** (`dasomweb/sale-automation-app`)
4. **Phase 1 시작** — Remix 앱 초기화 + Railway 배포

이 계획서를 바탕으로 진행할지, 또는 조정할 부분이 있는지 알려주세요.
