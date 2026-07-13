# StoreForge — 현재 상태 및 인수인계

**최종 갱신**: 2026-07-13
**브랜치**: `feat/storeforge-phase0` (main 미머지)
**기획안**: [storeforge-plan-v1.1.md](storeforge-plan-v1.1.md)

---

## 🔴 다음 세션에서 바로 할 것

### 1. StoreForge 전용 Shopify 앱 만들기 (사용자 액션)

나누기 스토어에 연동은 됐지만 **`write_metafields` 스코프가 없어 브랜드 주입이 막혀 있다.**

기존 앱(`Nanugi Theme Push`)은 **dev dashboard 로 관리되는 앱**이라 스코프를 체크박스로 못 바꾼다 —
`shopify.app.toml` + `shopify app deploy` 로 새 앱 버전을 배포해야 한다.
그런데 이 앱은 **GitHub Actions 테마 배포의 생명줄**이라 건드리면 배포가 깨질 수 있다.

**→ 그래서 StoreForge 전용 커스텀 앱을 따로 만든다. (테마 앱은 그대로 둔다)**

```
1. https://admin.shopify.com/store/nanugi/settings/apps/development
   ⚠️ dev.shopify.com 이 아니라 admin.shopify.com 이다 (다른 화면)
2. 앱 만들기 → 이름 "StoreForge"
3. Admin API 통합 구성 → 스코프:
     ✅ write_metafields   (필수 — 브랜드 주입)
     ✅ read_products      (권장 — 연결 확인 + 축②)
4. 저장 → 앱 설치
5. Admin API 액세스 토큰 공개 → shpat_… 복사 (한 번만 보인다)
```

**왜 앱을 분리하나**: 테마 배포용 앱과 브랜드 주입용 앱이 분리되면 하나가 망가져도 다른 하나가 안 죽고,
각자 최소 스코프만 갖는다. 기획안 §6 의 "커스텀 앱 우선" 전략과도 맞는다.

### 2. StoreForge 에서 자격증명 교체

관리자 페이지 → 나누기 스튜디오 → **자격증명 교체** → **액세스 토큰** 방식 → `shpat_…` 붙여넣기 → 저장

→ 연결 테스트가 자동으로 돌고, 스코프에 `✓ write_metafields` 가 뜨면 **주입 버튼이 활성화**된다.

### 3. 그 다음 (같은 세션에서 이어서)

- 나누기 브랜드를 AI 로 해석 → 실제 스토어에 metafield 주입 → 주입값 검증
- **홈 레이아웃 프리셋 5~8종** (기획안 §4.4 — 0주차 마지막 조각)
- 폰트 `.woff2` 파일을 테마 `assets/` 에 업로드 (지금은 fallback 스택으로 렌더됨)
- 테마 브랜치 PR → 라이브 반영 (이게 되어야 눈으로 색이 바뀌는 걸 볼 수 있다)

---

## 🟢 지금 살아있는 것

### 프로덕션 (Railway — 프로젝트 `DWSTUDIO Shopify`)

| | |
|---|---|
| 관리자 페이지 | https://web-production-6d2e0.up.railway.app |
| API | https://api-production-7afa.up.railway.app |
| 대시보드 | https://railway.com/project/87e2918e-6d1e-40ca-a26f-2f44921ed9fe |

**서비스 3개**: Postgres · api (FastAPI/Docker) · web (Next.js standalone/Docker)

**로그인**: `dasomweb@gmail.com` / 비밀번호는 Railway → api → Variables → `STOREFORGE_BOOTSTRAP_PASSWORD`
관리자 페이지 **계정** 메뉴에서 변경 가능 (변경 후 Railway 의 임시 비밀번호는 폐기할 것).

**배포 명령** (모노레포이므로 `--path-as-root` 필수):
```bash
cd storeforge
railway up ./api --path-as-root --service api --ci
railway up ./web --path-as-root --service web --ci
```

### 연동 상태

| 스토어 | 연결 | 스코프 |
|---|---|---|
| 나누기 스튜디오 (`nanugi.myshopify.com`) | ✅ 연결됨 | `read_themes`, `write_themes` — **`write_metafields` 없음 → 주입 차단** |

인증은 `client_credentials` (기존 `Nanugi Theme Push` 앱의 Client ID/Secret 재사용).
전용 앱을 만들면 `token` 방식으로 교체할 예정.

---

## 완료된 것

### 테마 개조 (0주차)

- **`snippets/brand-overrides.liquid`** (신규) — `shop.metafields.storeforge.brand` 를 읽어
  `--color-*` / `--font-*` CSS 변수를 덮어쓴다. `color-schemes` 직후에 렌더되어야 캐스케이드가 성립.
  metafield 가 없으면 **아무것도 출력하지 않는다** → 미설치 스토어에 영향 없음.
- **`layout/theme.liquid`** — 오버라이드 훅 + 페이지 폭(body 클래스라 CSS 변수로 못 덮음) metafield 우선순위.
- Liquid 에서 색 연산을 하지 않는다. 앱이 계산한 변수 맵을 그대로 출력만 하므로 **변수를 추가해도 테마를 다시 안 건드려도 된다.**

### 파생 엔진 (축① 핵심 IP)

`storeforge/api/app/engine/palette.py`

나누기 테마의 컬러는 **9스킴 × 35키 = 315개**. LLM 에게 이걸 생성시키면 반드시 깨진다.
→ **LLM 은 색 3~4개만 고르고**, 엔진이 결정론적으로 441개 CSS 변수를 전개하며 **WCAG 대비를 코드로 보정**한다.

**무작위 브랜드 500건 퍼징에서 WCAG 실패 0건.** 이것이 "AI 가 나쁜 색을 골라도 스토어가 안 깨지는" 이유다.

### LLM 브랜드 해석 (축①)

`storeforge/api/app/llm.py` — Claude Opus 4.8, 구조화 출력(json_schema).

3중 방어: ① 구조화 출력(형태 이탈 불가) ② enum 폰트 화이트리스트 ③ Pydantic 검증 + 재생성 루프(최대 3회).

프로덕션 실호출 검증 완료. 한인 B2B 케이스에서 "대량 카탈로그" 문장으로부터
페이지 폭 `wide` 와 한글 디스플레이 폰트(Gmarket Sans)까지 끌어냈다.

### 백엔드 / 관리자 페이지

- 인증 + **RBAC 3단계** (superadmin / admin / owner). 스토어 접근은 `StoreMember` 로 스코핑.
  **권한 없는 스토어는 403 이 아니라 404** 를 준다 — 존재 여부조차 노출하지 않는다. 침투 테스트 통과.
- **스토어별 자격증명** (프로젝트마다 따로). `client_credentials`(권장) / `token` 두 방식.
  모든 비밀값 Fernet 암호화, 응답에 절대 실리지 않음.
- **스코프 확인 UI** — 연결 테스트 시점에 부여된 스코프를 읽어 표시.
  `write_metafields` 가 없으면 주입 단계에서 **409 로 막는다** (Shopify 403 을 맞고 원인을 짐작하는 것보다 낫다).
- 계정 관리 (이름/이메일/비밀번호 변경, 슈퍼어드민의 타 사용자 비밀번호 재설정).
- 9개 컬러 스킴 실시간 미리보기 + WCAG 대비비 표시.
- Playwright 로 로그인 → 스토어 → 주입 화면까지 E2E 구동 확인 (로컬·프로덕션 양쪽).

---

## 반드시 알고 있어야 할 함정

1. **`main` 에 푸시하면 GitHub Actions 가 라이브 나누기 테마에 즉시 배포한다.**
   테마 파일(`theme.liquid`, `brand-overrides.liquid`)을 건드렸으므로 반드시 PR 리뷰 후 머지할 것.

2. **프로덕션 비밀값을 자동 생성하면 안 된다.**
   `STOREFORGE_TOKEN_ENCRYPTION_KEY` 가 재배포마다 바뀌면 **저장된 Shopify 토큰을 전부 복호화할 수 없다.**
   그래서 프로덕션에서는 비밀값이 없으면 **기동을 거부**하도록 만들어 뒀다 (`app/config.py`). 이 가드를 풀지 말 것.

3. **`app/shopify.py` 에 `themeFilesUpsert` 를 추가하고 싶어지면 기획안 §4.5 를 먼저 읽을 것.**
   테마 파일을 쓰지 않는 것이 `write_themes`(보호 스코프)를 피한 이유다. 그 순간 Phase 3 병목이 되살아난다.

4. **Railway 배포는 `--path-as-root` 없이 하면 상위 폴더를 통째로 올려서 실패한다.**

5. **Next.js 는 취약점이 있으면 Railway 가 배포를 차단한다.** 현재 14.2.35.
   남은 high 취약점들은 Next 16 에서만 패치된다(major, React 19 동반) — 후속 과제.

---

## 남은 과제

- [ ] StoreForge 전용 앱 + `write_metafields` → **실제 브랜드 주입** (다음 세션 첫 번째)
- [ ] 홈 레이아웃 프리셋 5~8종 (기획안 §4.4)
- [ ] 폰트 `.woff2` 파일을 테마 `assets/` 에 업로드 (Pretendard, Noto Sans KR, Gmarket Sans, Bebas Neue, Oswald, Roboto, Inter, Playfair Display)
- [ ] 테마 브랜치 PR → 라이브 반영
- [ ] Next.js 16 업그레이드 (남은 취약점)
- [ ] Alembic 도입 (지금은 `db.py` 의 멱등 ALTER 로 버티는 중 — 데이터 쌓이면 필요)
- [ ] **축② (ListPilot 상품/컬렉션 자동 구축) 미착수** ← 기획안상 진짜 해자
