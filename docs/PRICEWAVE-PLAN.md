# Pricewave — 개발 계획서

**Pricewave** — Shopify Sale 자동화 앱.
세일이 파도처럼 밀려왔다가 빠지듯, 스케줄에 맞춰 자동으로 가격이 변하고 복구됩니다.

> *Tagline*: "Ride the sale wave. Automatically."

스케줄 기반 할인, 컬렉션/태그 일괄 적용, sale 배지 자동 표시.

**전략**: 자체 클라이언트(DWSTUDIO)용으로 먼저 개발·운영하며 안정화 → **Shopify App Store 공개 판매**로 확장.

**진행 방식**: 이 테마 repo와 분리된 **별도 프로젝트**로 개발.

---

## 목차

1. [프로젝트 개요](#1-프로젝트-개요)
2. [핵심 기능 (MVP)](#2-핵심-기능-mvp)
3. [시스템 아키텍처](#3-시스템-아키텍처)
4. [데이터 모델](#4-데이터-모델)
5. [핵심 플로우](#5-핵심-플로우)
6. [테마 측 통합](#6-테마-측-통합)
7. [Rate Limit 관리 전략](#7-rate-limit-관리-전략) ⭐
8. [Bulk Operations & Staged Upload](#8-bulk-operations--staged-upload) ⭐
9. [다중 스토어 동시성](#9-다중-스토어-동시성)
10. [모니터링 및 관측성](#10-모니터링-및-관측성)
11. [개발 단계 (Phase)](#11-개발-단계-phase)
12. [비용](#12-비용)
13. [고려사항 / 리스크](#13-고려사항--리스크)
14. [다음 단계](#14-다음-단계)

---

## 1. 프로젝트 개요

| 항목 | 내용 |
|------|------|
| **앱 이름** | **Pricewave** |
| **배포 1단계** | Custom Distribution (DWSTUDIO 클라이언트 스토어) |
| **배포 2단계** | **Public on Shopify App Store** (안정화 후) |
| **첫 타겟 스토어** | nanugi.myshopify.com |
| **Tech Stack** | Remix + Node.js + Prisma + BullMQ |
| **DB** | PostgreSQL (Railway) |
| **Job Queue** | Redis + BullMQ (Railway) |
| **호스팅** | Railway (초기) → 트래픽 증가 시 Fly.io 또는 AWS 검토 |
| **저장소** | 새 GitHub repo: `dasomweb/pricewave` (별도 프로젝트) |
| **수익 모델** | Freemium (Free + $9.99/$19.99/$49.99 plans) |

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
          │ Polaris UI                  │ Admin API + Bulk Operations
          │ (Remix routes)              │
          ▼                             ▼
┌─────────────────────────────────────────────────────────┐
│                    Pricewave                   │
│                  (Railway, Remix server)                 │
│                                                          │
│  ┌────────────┐  ┌─────────────┐  ┌─────────────────┐  │
│  │ OAuth 인증  │  │ Webhook 수신 │  │  Scheduler      │  │
│  │ (세션 저장) │  │ (제거/충돌)  │  │ (cron 5min)    │  │
│  └────────────┘  └─────────────┘  └────────┬────────┘  │
│                                             │            │
│                                             ▼            │
│                              ┌─────────────────────┐    │
│                              │  Job Queue (BullMQ) │    │
│                              │  Per-store worker   │    │
│                              └──────────┬──────────┘    │
│                                         │               │
│                              ┌──────────▼──────────┐    │
│                              │  Sale Executor      │    │
│                              │  (Bulk Operations)  │    │
│                              └──────────┬──────────┘    │
│                                         │               │
└─────────────────────────────────────────┼───────────────┘
                                          │
                       ┌──────────────────┼──────────────────┐
                       ▼                  ▼                  ▼
           ┌──────────────────┐ ┌──────────────────┐ ┌──────────────┐
           │   PostgreSQL     │ │  Redis (BullMQ)  │ │   Sentry     │
           │   - Stores       │ │  - sale-jobs     │ │   PostHog    │
           │   - Sales        │ │  - retries       │ │              │
           │   - SaleSnapshots│ │                  │ │              │
           └──────────────────┘ └──────────────────┘ └──────────────┘
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
  timezone     String?  // shop API에서 가져옴
  installedAt  DateTime @default(now())
  uninstalledAt DateTime?

  sales        Sale[]
  bulkOperations BulkOperation[]
}

model Sale {
  id           String   @id @default(cuid())
  store        Store    @relation(fields: [storeId], references: [id])
  storeId      String

  name         String
  status       SaleStatus  // SCHEDULED | STARTING | ACTIVE | ENDING | ENDED | FAILED | CANCELLED

  startsAt     DateTime
  endsAt       DateTime

  discountType DiscountType  // PERCENTAGE | FIXED_AMOUNT
  discountValue Decimal

  targetType   TargetType    // COLLECTION | TAG | PRODUCTS | ALL
  targetIds    String[]

  badgeText    String?

  // 실행 추적
  startedAt    DateTime?
  endedAt      DateTime?
  failureReason String?

  createdAt    DateTime @default(now())
  updatedAt    DateTime @updatedAt

  snapshots    SaleSnapshot[]

  @@index([status, startsAt, endsAt])
  @@index([storeId])
}

model SaleSnapshot {
  // 세일 적용 전 원래 가격 백업 — 종료 시 복구용
  id            String   @id @default(cuid())
  sale          Sale     @relation(fields: [saleId], references: [id])
  saleId        String

  productId     String   // gid://shopify/Product/...
  variantId     String   // gid://shopify/ProductVariant/...
  originalPrice Decimal
  originalCompareAtPrice Decimal?

  appliedAt     DateTime @default(now())
  revertedAt    DateTime?
  status        SnapshotStatus @default(PENDING)  // PENDING | APPLIED | REVERTED | FAILED

  @@index([saleId, status])
  @@index([variantId])
}

model BulkOperation {
  // Shopify Bulk Operation 추적
  id           String   @id @default(cuid())
  store        Store    @relation(fields: [storeId], references: [id])
  storeId      String

  shopifyId    String   @unique  // gid://shopify/BulkOperation/...
  saleId       String?  // 어떤 sale의 작업인지
  operation    String   // "START_SALE" | "END_SALE"
  status       String   // CREATED | RUNNING | COMPLETED | FAILED | CANCELED
  resultUrl    String?  // 결과 jsonl 다운로드 URL
  objectCount  Int?

  createdAt    DateTime @default(now())
  completedAt  DateTime?
}

enum SaleStatus {
  SCHEDULED
  STARTING    // bulk operation 진행 중
  ACTIVE
  ENDING      // 종료 bulk operation 진행 중
  ENDED
  FAILED
  CANCELLED
}

enum DiscountType { PERCENTAGE FIXED_AMOUNT }
enum TargetType { COLLECTION TAG PRODUCTS ALL }
enum SnapshotStatus { PENDING APPLIED REVERTED FAILED }
```

---

## 5. 핵심 플로우

### 5.1 세일 시작 (Scheduler가 매 5분마다 체크)

```
[Scheduler]
  1. SELECT * FROM sales WHERE status='SCHEDULED' AND startsAt <= NOW()
  2. 각 Sale을 store별 Job Queue에 enqueue

[Worker per store]
  3. Sale.status = 'STARTING'
  4. 대상 variant 목록 결정 (collection/tag/products GraphQL 조회)

  5. 분기:
     - variant 50개 미만 → GraphQL 단일 mutation (즉시 처리)
     - variant 50개 이상 → Bulk Operations (비동기 처리)

  6. Snapshot 저장 (status=PENDING):
     for each variant: { variantId, originalPrice, originalCompareAtPrice }

  7. Bulk Operations 실행 → Section 8 참고

  8. 완료 webhook 수신 → SaleSnapshot.status = 'APPLIED'
                       → Sale.status = 'ACTIVE'
```

### 5.2 세일 종료

```
[Scheduler]
  1. SELECT * FROM sales WHERE status='ACTIVE' AND endsAt <= NOW()

[Worker]
  2. Sale.status = 'ENDING'
  3. SaleSnapshot 조회 (status=APPLIED)
  4. Bulk Operations 실행 (price/compareAtPrice 복구 + metafield 삭제)
  5. 완료 webhook → SaleSnapshot.status = 'REVERTED', Sale.status = 'ENDED'
```

### 5.3 멱등성 보장

- Scheduler가 중복 실행되어도 안전: `SELECT FOR UPDATE` + 상태 머신
- 이미 STARTING/ACTIVE인 Sale은 재처리 안 함
- 이미 ENDING/ENDED인 Sale은 재복구 안 함
- Job ID로 BullMQ 자체 중복 제거 (`jobId: 'start-sale-${saleId}'`)

---

## 6. 테마 측 통합

이 앱과 함께 동작하려면 클라이언트 테마(NANUGI 등)에 metafield 노출 코드 추가.

**상품 카드 (`blocks/_product-card.liquid`)**:
```liquid
{%- liquid
  assign sale_badge = product.metafields.custom.sale_badge
-%}
{%- if sale_badge != blank -%}
  <span class="sale-badge">{{ sale_badge }}</span>
{%- endif -%}
```

**상품 페이지 (`blocks/_product-details.liquid`)**: 동일.

→ NANUGI 테마에는 추후 별도 PR로 추가.

---

## 7. Rate Limit 관리 전략

Shopify API rate limit은 앱의 안정성에 가장 큰 영향을 미치는 요소. 4가지 방어선으로 보호.

### 7.1 Shopify의 3가지 API 모델

| API | 모델 | 한도 | 용도 |
|-----|------|------|------|
| **REST Admin** | Leaky Bucket | 2 req/s (Standard), 4 req/s (Plus) | 단순 작업, deprecated 추세 |
| **GraphQL Admin** | Cost-based | 1000 points budget, 50 pts/s 회복 | 일반 작업 (권장) |
| **Bulk Operations** | Async | 사실상 무제한 | 대량 처리 (필수) |

### 7.2 방어선 1: 적절한 API 선택

```
변경 variant 수 < 50    → GraphQL 단일 mutation (실시간)
50 ≤ variant 수 < 500   → GraphQL 배치 (5~10개씩)
variant 수 ≥ 500        → Bulk Operations 필수
```

### 7.3 방어선 2: Throttling (BullMQ + Bottleneck)

```javascript
// 스토어별 limiter
const limiters = new Map()

function getLimiter(shop) {
  if (!limiters.has(shop)) {
    limiters.set(shop, new Bottleneck({
      minTime: 100,                      // 호출 간 최소 100ms
      maxConcurrent: 5,                  // 동시 5개까지
      reservoir: 1000,                   // GraphQL cost budget
      reservoirRefreshAmount: 1000,
      reservoirRefreshInterval: 1000     // 1초마다 회복
    }))
  }
  return limiters.get(shop)
}

await getLimiter(shop).schedule(() => shopify.graphql(query))
```

### 7.4 방어선 3: Cost-aware Throttling

GraphQL 응답의 `extensions.cost.throttleStatus.currentlyAvailable`을 추적:

```javascript
const response = await shopify.graphql(query)
const remaining = response.extensions?.cost?.throttleStatus?.currentlyAvailable ?? 1000

if (remaining < 100) {
  await sleep(2000)  // 회복 대기
}
```

### 7.5 방어선 4: Exponential Backoff (재시도)

```javascript
async function callWithRetry(fn, maxRetries = 5) {
  for (let i = 0; i < maxRetries; i++) {
    try {
      return await fn()
    } catch (err) {
      if (err.code === 429 || err.code === 'THROTTLED') {
        const wait = Math.min(1000 * Math.pow(2, i), 30000)  // 1s → 30s
        await sleep(wait)
        continue
      }
      throw err
    }
  }
  throw new Error('Max retries exceeded')
}
```

---

## 8. Bulk Operations & Staged Upload

대량 변경의 표준 패턴. **Shopify의 임시 저장소(Staged Upload)에 데이터를 올리고 처리를 위임**하는 방식.

### 8.1 전체 흐름

```
[우리 앱]                                    [Shopify]

  1. stagedUploadsCreate ────────────────►  임시 URL 발급
        (업로드 공간 신청)                    (gs://shopify-tmp/abc123)

  2. JSONL 데이터 업로드 ─────────────────►  임시 저장소에 보관
        (1000개 변경 사항)

  3. bulkOperationRunMutation ────────────►  처리 시작
        (실행 명령)                            ↓
                                              백그라운드 처리
  4.        ◄──── webhook (완료 알림) ────  (수 분 ~ 수십 분)
                                              ↓
  5. 결과 jsonl 다운로드  ◄────────────────  결과 파일 생성
        (성공/실패 확인)
```

### 8.2 Step별 코드 예시

**Step 1: Staged Upload URL 신청**
```javascript
const { stagedUploadsCreate } = await shopify.graphql(`
  mutation stagedUploadsCreate($input: [StagedUploadInput!]!) {
    stagedUploadsCreate(input: $input) {
      stagedTargets {
        url
        resourceUrl
        parameters { name value }
      }
      userErrors { field message }
    }
  }
`, {
  input: [{
    resource: 'BULK_MUTATION_VARIABLES',
    filename: `sale-${saleId}-start.jsonl`,
    mimeType: 'text/jsonl',
    httpMethod: 'POST'
  }]
})

const target = stagedUploadsCreate.stagedTargets[0]
```

**Step 2: JSONL 파일 생성 + 업로드**
```javascript
// JSONL 한 줄 = 한 variant 변경
const jsonl = snapshots.map(s => JSON.stringify({
  input: {
    id: s.variantId,
    price: calculateDiscountedPrice(s.originalPrice, sale).toString(),
    compareAtPrice: s.originalPrice.toString()
  }
})).join('\n')

// FormData로 업로드 (Shopify staged upload는 multipart 요구)
const formData = new FormData()
target.parameters.forEach(p => formData.append(p.name, p.value))
formData.append('file', new Blob([jsonl], { type: 'text/jsonl' }))

await fetch(target.url, { method: 'POST', body: formData })
```

**Step 3: Bulk Mutation 실행**
```javascript
const { bulkOperationRunMutation } = await shopify.graphql(`
  mutation bulkOperationRunMutation($mutation: String!, $stagedUploadPath: String!) {
    bulkOperationRunMutation(mutation: $mutation, stagedUploadPath: $stagedUploadPath) {
      bulkOperation { id status }
      userErrors { field message }
    }
  }
`, {
  mutation: `
    mutation call($input: ProductVariantInput!) {
      productVariantUpdate(input: $input) {
        productVariant { id price compareAtPrice }
        userErrors { field message }
      }
    }
  `,
  stagedUploadPath: target.resourceUrl
})

// DB에 BulkOperation 저장
await prisma.bulkOperation.create({
  data: {
    storeId,
    saleId,
    shopifyId: bulkOperationRunMutation.bulkOperation.id,
    operation: 'START_SALE',
    status: 'CREATED'
  }
})
```

**Step 4: 완료 Webhook 처리**
```javascript
// /webhooks/bulk-operations/finish
app.post('/webhooks/bulk-operations/finish', async (req, res) => {
  const { admin_graphql_api_id, status, url, object_count } = req.body

  const bulkOp = await prisma.bulkOperation.update({
    where: { shopifyId: admin_graphql_api_id },
    data: { status, resultUrl: url, objectCount: object_count, completedAt: new Date() }
  })

  if (status === 'completed') {
    // Sale.status = ACTIVE (또는 ENDED) 업데이트
    if (bulkOp.operation === 'START_SALE') {
      await prisma.sale.update({
        where: { id: bulkOp.saleId },
        data: { status: 'ACTIVE', startedAt: new Date() }
      })
      await prisma.saleSnapshot.updateMany({
        where: { saleId: bulkOp.saleId, status: 'PENDING' },
        data: { status: 'APPLIED' }
      })
    }
    // ... END_SALE도 유사하게
  }

  res.status(200).end()
})
```

**Step 5: 결과 파일 검증 (선택)**
```javascript
const result = await fetch(bulkOp.resultUrl)
const lines = (await result.text()).split('\n').filter(Boolean)
const failures = lines
  .map(JSON.parse)
  .filter(item => item.userErrors?.length > 0)

if (failures.length > 0) {
  // Sentry 알림 + DB 기록 + 부분 재시도
}
```

### 8.3 임시 저장소의 수명

- **업로드 URL**: 수시간 유효 (그 안에 PUT/POST 완료 필요)
- **업로드된 파일**: Shopify 처리 중에만 유지, 처리 끝나면 자동 삭제
- **결과 파일**: **약 7일** 유지 → 7일 안에 다운로드/검증 필요

### 8.4 Bulk Operations vs 일반 GraphQL 비교

| 항목 | 일반 GraphQL | Bulk Operations |
|------|--------------|----------------|
| **API 호출 수** (1000건 기준) | 1000번 | **3번** |
| **소요 시간** | 약 8분 | 약 1~3분 (백그라운드) |
| **우리 앱 부하** | 8분간 worker 점유 | 5초 후 sleep |
| **Rate limit** | 매번 신경 | 무관 |
| **실패 처리** | 매 호출마다 | 결과 파일 일괄 |
| **추적** | 응답 즉시 | webhook 비동기 |

---

## 9. 다중 스토어 동시성

### 9.1 핵심 원칙
- **각 스토어마다 독립적인 rate limit budget**
- 한 스토어 문제가 다른 스토어에 영향 주면 안 됨

### 9.2 BullMQ + Per-store Queue

```javascript
// Redis 위에 BullMQ로 스토어별 queue
const queues = new Map()

function getQueue(shop) {
  if (!queues.has(shop)) {
    queues.set(shop, new Queue(`sale-${shop}`, {
      connection: redisConnection,
      defaultJobOptions: {
        attempts: 5,
        backoff: { type: 'exponential', delay: 2000 },
        removeOnComplete: 100,  // 최근 100건만 보관
        removeOnFail: 500
      }
    }))
  }
  return queues.get(shop)
}

// Scheduler가 sale을 큐잉
await getQueue(shop).add('start-sale', { saleId }, {
  jobId: `start-sale-${saleId}`  // 중복 방지
})

// 스토어별 worker (concurrency=1로 직렬화)
new Worker(`sale-${shop}`, async (job) => {
  await processSaleStart(job.data.saleId)
}, { connection: redisConnection, concurrency: 1 })
```

### 9.3 동시 처리 시나리오

```
00:00:00  Scheduler: 5개 스토어에서 시작 sale 발견
          ↓
00:00:01  각 스토어 큐에 작업 enqueue (병렬)
          ├── nanugi:queue        → enqueue
          ├── client-b:queue      → enqueue  
          ├── client-c:queue      → enqueue
          ├── client-d:queue      → enqueue
          └── client-e:queue      → enqueue

00:00:02  Worker 5개가 병렬 실행
          ├── nanugi worker     → variant 200개 → GraphQL 배치 (~1분)
          ├── client-b worker   → variant 5000개 → Bulk Op 시작
          ├── client-c worker   → variant 50개 → 단일 mutation (~10초)
          ├── client-d worker   → variant 1000개 → Bulk Op 시작
          └── client-e worker   → variant 100개 → GraphQL 배치 (~30초)

각 worker는 자기 스토어의 rate limit만 신경쓰면 됨.
한 worker가 실패해도 다른 worker 영향 없음.
```

---

## 10. 모니터링 및 관측성

### 10.1 핵심 메트릭

```
[운영 대시보드 예시]
┌──────────────────────────────────────────────────────┐
│ 스토어         | API 사용률 | 429 횟수 | Active Sales │
│ nanugi         |    23%    |    0    |      2       │
│ client-b       |    87% ⚠️ |   12 ⚠️ |      5       │
│ client-c       |     5%    |    0    |      0       │
└──────────────────────────────────────────────────────┘

[Sale 실행 통계]
- Today: 12 sales started, 8 ended, 0 failed
- This week: 87 sales, success rate 99.2%
- Avg execution time: 47s (start), 31s (end)
```

### 10.2 알림 정책

| 상황 | 채널 | 우선순위 |
|------|------|---------|
| Sale 실행 실패 | Sentry + 이메일 | High |
| Bulk Operation 7일 후에도 미완료 | Sentry | Medium |
| API 사용률 80%+ | Slack | Low |
| 429 응답 분당 10+ | Slack + 자동 throttling | Medium |
| Queue 적체 (job > 100) | Slack | High |

### 10.3 도구

- **Sentry**: 에러 추적 (Free → Team $26/월)
- **PostHog**: 사용 분석 (Free 1M events)
- **Railway Metrics**: 인프라 메트릭 (기본 제공)
- **Custom Dashboard**: Remix 페이지로 admin 전용 대시보드

---

## 11. 개발 단계 (Phase)

### **STAGE 1 — 자체 운영 (MVP, ~6주)**

#### Phase 1: 기반 구축 (1주)
- [ ] Shopify Partner 계정 생성, 새 앱 등록 (Custom + 향후 Public 전환 가능 설정)
- [ ] Remix 프로젝트 초기화 (`npm init @shopify/app@latest`)
- [ ] Railway 프로젝트 생성: app + PostgreSQL + Redis
- [ ] OAuth 인증 플로우 동작 확인
- [ ] DB 마이그레이션 (Prisma)
- [ ] BullMQ + Redis 연결
- [ ] 기본 임베드 UI (Polaris) 띄우기
- [ ] **GDPR webhook endpoint 3개** (customers/data_request, customers/redact, shop/redact)
- [ ] **에러 추적** (Sentry 연동)

#### Phase 2: Sale CRUD (1주)
- [ ] Sale 생성 폼 (이름, 기간, 할인, 대상)
- [ ] Sale 목록/상세 페이지
- [ ] 대상 상품 목록 미리보기 (Admin API GraphQL)
- [ ] Sale 수정/취소
- [ ] 대상 상품 검색/필터링 UI

#### Phase 3: 실행 엔진 — Rate Limit & Bulk Operations (2주)
- [ ] Scheduler (cron 5min)
- [ ] BullMQ per-store queue 구조
- [ ] **Bulk Operations 통합**:
  - Staged Upload URL 발급
  - JSONL 생성 및 업로드
  - bulkOperationRunMutation 실행
  - Webhook 수신 (`bulk_operations/finish`)
  - 결과 파일 다운로드 및 검증
- [ ] **Rate Limit 방어선 4단계 구현**:
  - 적절한 API 선택 로직 (variant 수 기준 분기)
  - Bottleneck throttling
  - Cost-aware monitoring
  - Exponential backoff retry
- [ ] Sale Executor: 시작 처리 (snapshot + 가격 변경 + 메타필드)
- [ ] Sale Executor: 종료 처리 (가격 복구 + 메타필드 삭제)
- [ ] 멱등성 검증 (단위 테스트 + 시나리오 테스트)

#### Phase 4: 안정화 + 테마 통합 (1주)
- [ ] Webhook 수신 (`app/uninstalled`, `products/update`)
- [ ] 가격 충돌 감지 및 처리
- [ ] NANUGI 테마에 sale badge 표시 코드 추가
- [ ] 통합 테스트 (실제 nanugi 스토어로 작은 세일 실행)
- [ ] **사용 분석 로깅** (PostHog)

#### Phase 5: 자체 운영 (1주)
- [ ] DWSTUDIO 클라이언트 1~3개 스토어에 Custom 배포
- [ ] 실 사용자 피드백 수집
- [ ] 버그 수정, UX 개선
- [ ] 운영 메트릭 모니터링 (성공률, 응답 시간, Shopify API rate)
- [ ] Admin 대시보드 (다중 스토어 상태 한눈에 보기)

**STAGE 1 결과물**: 자체 클라이언트가 안정적으로 사용 중인 검증된 앱.

---

### **STAGE 2 — App Store 공개 (~3주)**

자체 운영 **최소 3~6개월** 후 시작. 안정성 데이터 충분히 확보된 시점.

#### Phase 6: App Store 준비 (1.5주)
- [ ] **Subscription/Billing 통합** (Shopify Billing API)
  - Free / Basic ($9.99) / Pro ($19.99) / Advanced ($49.99)
  - Free trial (7~14일)
- [ ] **다국어 지원** (영어 필수, 한국어 + 1~2개)
- [ ] **App listing 자료**: 아이콘, 스크린샷 5~7장, 데모 비디오, 영문 카피
- [ ] **Privacy Policy / Terms of Service** 페이지
- [ ] **Support 채널** (이메일 또는 Crisp/Intercom)

#### Phase 7: Built for Shopify 인증 준비 (0.5주, 선택)
- [ ] Performance 요구사항 충족 (TTI < 3s, Lighthouse score)
- [ ] Built for Shopify 배지 신청

#### Phase 8: 심사 제출 + 대응 (1주)
- [ ] App Store 심사 제출
- [ ] 거절 사유 대응
- [ ] Soft launch

**STAGE 2 결과물**: Shopify App Store에 공개된 유료 앱.

---

**전체 타임라인**:
- STAGE 1 (MVP + 자체 운영): **6주**
- 자체 운영 안정화: **3~6개월** (실 사용 데이터)
- STAGE 2 (App Store 공개): **3주**
- **총 ~5~7개월** (MVP 출시부터 App Store 등재까지)

---

## 12. 비용

### STAGE 1 (자체 운영)
| 항목 | 비용 |
|------|------|
| Shopify Partner 계정 | 무료 |
| Railway (Hobby) — App | $5/월 |
| Railway PostgreSQL | $5/월 |
| Railway Redis | $5/월 |
| Sentry (Free) | 무료 |
| PostHog (Free) | 무료 |
| 도메인 | $12/년 |
| **합계** | **~$15~20/월** |

### STAGE 2 (App Store 공개) — 100~500 인스톨
| 항목 | 비용 |
|------|------|
| Railway Pro — App | $20/월 |
| Railway PostgreSQL | $20/월 |
| Railway Redis | $10/월 |
| Sentry (Team) | $26/월 |
| Resend (이메일) | $20/월 |
| Crisp (Support) | $25/월 |
| **합계** | **~$120/월** |

### 수익 예측
- 평균 ARPU: $15/월
- 100 paid 인스톨: $1,500 MRR (이익 ~$1,380)
- 1,000 paid 인스톨: $15,000 MRR (이익 ~$13,800)
- **Shopify 수수료**: 매출의 15~20% 차감

---

## 13. 고려사항 / 리스크

### 13.1 가격 충돌
- **문제**: 클라이언트가 세일 진행 중에 수동으로 상품 가격 변경 → snapshot 정합성 깨짐
- **대응**: webhook `products/update` 수신 → 세일 진행 중인 상품이면 snapshot 갱신 + 알림

### 13.2 다중 세일 중첩
- **문제**: 같은 상품에 두 세일이 동시 적용
- **대응**: MVP에서는 "한 상품당 한 세일만 active" 제약. 추후 priority 기능 추가.

### 13.3 Bulk Operation 실패
- **문제**: Bulk operation이 부분 실패 (일부 variant만 실패)
- **대응**: 결과 파일 파싱 → 실패한 variant만 재시도

### 13.4 시간대 (Timezone)
- **문제**: 세일 시간을 어느 시간대로 받을지
- **대응**: 클라이언트 로컬 시간으로 입력받되 DB는 UTC. 스토어 timezone은 Shopify Shop API에서 가져옴.

### 13.5 환불/캐시
- **문제**: compare_at_price는 즉시 반영되지만 CDN 캐시 때문에 일부 페이지에서 지연
- **대응**: 클라이언트에 "최대 5분 지연" 안내

### 13.6 앱 제거 시 정리
- **문제**: 클라이언트가 앱 제거하는데 세일 진행 중이면? 가격이 할인된 채로 멈춤
- **대응**: `app/uninstalled` webhook → 진행 중 세일 즉시 종료 + 가격 복구
- **추가 안전장치**: 우리가 가격을 망가뜨리지 않도록 snapshot 검증 강화

### 13.7 Free Tier 남용
- **문제**: 무료로 무제한 세일 가능하면 서버 비용 폭증
- **대응**: Free tier에 active sale 수 제한 (예: 동시 1개)

---

## 14. 다음 단계

1. **계획서 검토 및 승인**
2. **Shopify Partner 계정 생성** ([partners.shopify.com](https://partners.shopify.com))
3. **새 GitHub repo 생성**: `dasomweb/pricewave`
4. **도메인 확보**: `pricewave.app` 또는 `pricewave.io` (구매 가능 여부 확인)
4. **이 문서를 새 repo로 이동**: `docs/PLAN.md`
5. **Phase 1 시작**:
   - Remix 앱 초기화
   - Railway 프로젝트 생성 (App + PostgreSQL + Redis)
   - OAuth + 기본 UI 띄우기
6. **Phase 2부터는 1주 단위로 진행 상황 리뷰**

---

## 부록 A: 참고 자료

- [Shopify App Development Docs](https://shopify.dev/docs/apps)
- [Shopify Bulk Operations](https://shopify.dev/docs/api/usage/bulk-operations/imports)
- [Shopify Rate Limits](https://shopify.dev/docs/api/usage/rate-limits)
- [Remix Shopify App Template](https://github.com/Shopify/shopify-app-template-remix)
- [BullMQ](https://docs.bullmq.io/)
- [Polaris Design System](https://polaris.shopify.com/)

---

이 계획서를 바탕으로 진행할지, 또는 조정할 부분이 있는지 알려주세요.
