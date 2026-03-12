# The Barber Spot 테마 배포 가이드 (Wiki)

이 문서는 **GitHub Actions**와 **Shopify Dev Dashboard 앱**을 사용해 The Barber Spot 스토어 테마를 배포하는 방식을 설명합니다.

---

## 1. 이 방식을 쓰는 이유

| 방식 | 설명 |
|------|------|
| **Theme Access 앱** | 서드파티 앱으로 토큰 발급 가능하지만, 평점·신뢰도 문제로 사용하지 않음. |
| **레거시 커스텀 앱** | 스토어 Admin에서 만드는 예전 방식. **2026년 1월 1일부터 새로 만들 수 없음.** |
| **Dev Dashboard 앱 + GitHub Actions** ✅ | Shopify 공식 흐름. Client ID/Secret만 발급받아 두고, 배포 시마다 24시간 유효 토큰을 받아 `theme push`에 사용. |

**정리:** 로컬에서 CLI 로그인 없이, **코드를 `main`에 push하기만 하면** GitHub Actions가 자동으로 테마를 배포합니다. 개발 이력은 Git으로, 배포는 Actions로 관리합니다.

---

## 2. 전체 흐름 개요

```
[로컬] 코드 수정 → git push origin main   (또는 태그 푸시: git tag v1.0.x && git push origin v1.0.x)
         ↓
[GitHub] main 푸시 또는 v* 태그 푸시 감지 → "Deploy Shopify Theme" 워크플로 실행
         ↓
[GitHub Actions] ① 저장소 체크아웃
                 ② Dev Dashboard 앱의 Client ID/Secret으로 Shopify에 토큰 요청 (24시간 유효)
                 ③ Shopify CLI 설치 후 theme push 실행
                 ④ (태그 푸시인 경우) GitHub Release 자동 생성
         ↓
[Shopify] 지정한 테마(153245647037)에 파일 반영
```

- **토큰:** Theme Access/레거시 앱의 장기 토큰을 쓰지 않고, **매 배포마다** Client credentials로 새 액세스 토큰을 받아 사용합니다.
- **대상:** Environment `shopify-thebarberspot`의 Secrets에 저장한 스토어·테마 ID로만 배포됩니다.

---

## 3. 사전 준비 (한 번만 하면 됨)

두 가지를 준비합니다.

1. **Shopify Dev Dashboard에서 앱 만들기** → Client ID, Client secret 발급  
2. **GitHub 저장소에 Environment·Secrets 설정** → 위 값과 스토어·테마 ID 저장  

---

## 4. Dev Dashboard 앱 만들기 (단계별)

배포에 필요한 **Client ID**와 **Client secret**은 여기서 만든 앱에서 가져옵니다.

### 4.1 Dev Dashboard 접속

- [dev.shopify.com](https://dev.shopify.com/dashboard/) 접속 후 로그인
- 왼쪽 메뉴에서 **Apps** 선택

### 4.2 앱 생성

- 오른쪽 상단 **Create app** 클릭
- **Start from Dev Dashboard** 선택
- 앱 이름 입력 (예: `Theme Push`, `The Barber Spot Theme Deploy`) 후 **Create** 클릭

### 4.3 버전(Version) 만들기

- 앱이 생성되면 **Versions** 탭으로 이동
- **Create version** 또는 **Release**로 새 버전 생성
- **Configuration**에서:

  - **Admin API integration** → **Edit**
  - **Access scopes**에 테마 권한 추가:
    - `read_themes` (테마 읽기)
    - `write_themes` (테마 쓰기)
  - UI에 "Theme templates and theme files" 관련 스코프가 있으면 **Read and write** 선택
  - **Save** 후 해당 버전을 **Release**로 배포

### 4.4 배포 방식(Distribution) 선택 ⚠️

**이 단계를 건너뛰면** 스토어에서 앱 설치 시 *"The app developer needs to select a distribution method first"* 오류가 납니다. 반드시 진행하세요.

- **Partners**: [partners.shopify.com](https://partners.shopify.com) → **Apps** → 해당 앱 선택  
- 또는 **Dev Dashboard**: 해당 앱 → **Distribution** / **App distribution** 메뉴로 이동  

이후:

1. **Choose distribution** (배포 방식 선택) 클릭
2. **Custom distribution** 선택 → **Select**
   - 이 앱은 The Barber Spot 한 스토어(또는 정해진 스토어)용이므로 **Custom**이 맞습니다.
   - **Public**은 앱스토어 공개용이므로 선택하지 않습니다.
3. (선택) Custom 선택 후 스토어 도메인(`thebarberspot.myshopify.com`) 입력하고 **Generate link**로 설치 링크 생성 가능

### 4.5 스토어에 앱 설치

- **Install** 버튼 클릭
- **Select store**에서 **The Barber Spot** 스토어 선택
- **Install app** 클릭하여 설치 완료

### 4.6 Client ID / Client secret 복사

- 앱 왼쪽 메뉴에서 **Settings** 선택
- **Client credentials** 영역에서:
  - **Client ID** 복사 → 나중에 GitHub Secret `SHOPIFY_CLIENT_ID`에 넣습니다.
  - **Client secret**의 **Reveal** 클릭 후 복사 → GitHub Secret `SHOPIFY_CLIENT_SECRET`에 넣습니다.

Client secret은 최초 1회만 노출될 수 있으므로 반드시 안전한 곳에 보관하세요.

---

## 5. GitHub Environment 및 Secrets 설정

배포는 **Environment** `shopify-thebarberspot`에 연결되어 있으며, 이 Environment의 **Secrets**만 사용합니다.

### 5.1 Environment 생성 (없는 경우)

- GitHub 저장소 → **Settings** → **Environments**
- **New environment** 클릭 후 이름에 **shopify-thebarberspot** 입력하여 생성

### 5.2 Environment secrets 추가

- **shopify-thebarberspot** Environment 선택 → **Environment secrets**에서 **Add secret**로 아래 4개 추가:

| Name | Value | 비고 |
|------|--------|------|
| `SHOPIFY_FLAG_STORE` | `thebarberspot.myshopify.com` | 배포 대상 스토어 |
| `SHOPIFY_CLIENT_ID` | (4.6에서 복사한 Client ID) | Dev Dashboard 앱 식별자 |
| `SHOPIFY_CLIENT_SECRET` | (4.6에서 복사한 Client secret) | 토큰 발급용 비밀값 |
| `SHOPIFY_THEME_ID` | `153245647037` | 배포할 테마 ID (에디터 URL에 포함) |

워크플로는 이 Environment를 사용하므로, **다른 브랜치나 저장소에는 이 Secrets가 노출되지 않습니다.**

---

## 6. 배포 방법 (일상 작업)

설정이 끝난 뒤에는 다음만 하면 됩니다.

- **자동 배포:** 로컬에서 `main` 브랜치로 push  
  ```bash
  git add .
  git commit -m "테마 수정 내용 요약"
  git push origin main
  ```
- **태그 배포 + 릴리즈:** 버전 태그를 푸시하면 배포 후 GitHub Release가 자동 생성됨  
  ```bash
  git tag v1.0.12 -m "Release v1.0.12 - 변경 요약"
  git push origin v1.0.12
  ```
- **수동 실행:** GitHub 저장소 → **Actions** → **Deploy Shopify Theme** → **Run workflow** → **Run workflow** 버튼 클릭

배포가 성공하면 지정한 테마(153245647037)에 변경 사항이 반영됩니다.  
테마 에디터: [The Barber Spot 테마 에디터](https://admin.shopify.com/store/thebarberspot/themes/153245647037/editor)

---

## 7. 워크플로가 하는 일 (참고)

`.github/workflows/deploy-theme.yml` 요약:

1. **Get Shopify access token**  
   `SHOPIFY_FLAG_STORE`, `SHOPIFY_CLIENT_ID`, `SHOPIFY_CLIENT_SECRET`으로  
   `https://{store}/admin/oauth/access_token`에 `grant_type=client_credentials` 요청 → 24시간 유효 `access_token` 획득.

2. **Install Shopify CLI**  
   Node 20 환경에서 `@shopify/cli`, `@shopify/theme` 전역 설치.

3. **Deploy theme**  
   받은 토큰을 `SHOPIFY_CLI_THEME_TOKEN`으로, 테마 ID를 `--theme` 인자로 넘겨  
   `shopify theme push --allow-live` 실행.

4. **Create GitHub Release** (태그 푸시 시에만)  
   `refs/tags/` 로 시작하는 ref일 때 `softprops/action-gh-release`로 해당 태그에 릴리즈 노트 자동 생성.

Theme Access 앱이나 레거시 커스텀 앱의 장기 토큰은 사용하지 않습니다.

---

## 8. 로컬 개발 (선택)

배포는 Actions에 맡기고, 로컬에서는 **미리보기**만 할 수 있습니다.

```bash
npm install -g @shopify/cli @shopify/theme
cd H:\GitHub\DWSTUDIO-TheBarberSpot
shopify theme dev
```

브라우저에서 스토어 로그인 후, 로컬 변경이 실시간으로 미리보기에 반영됩니다.  
실제 테마 반영은 `git push origin main` 후 Actions 배포로 이루어집니다.

---

## 9. 문제 해결

| 상황 | 확인 사항 |
|------|-----------|
| "The app developer needs to select a distribution method first" | 4.4 배포 방식에서 **Custom distribution** 선택 여부 확인. |
| "Failed to get access token" | `SHOPIFY_CLIENT_ID`, `SHOPIFY_CLIENT_SECRET`, `SHOPIFY_FLAG_STORE` 값과 앱 설치 스토어가 일치하는지 확인. |
| 배포는 되는데 테마가 안 바뀜 | `SHOPIFY_THEME_ID`가 에디터 URL의 테마 ID와 같은지 확인. |
| 다른 스토어/테마로 배포하고 싶음 | 새 Environment를 만들거나, 기존 Environment의 Secrets만 해당 스토어·테마·앱 값으로 교체. (워크플로는 동일하게 `shopify-thebarberspot` 사용 가능) |

---

## 10. 요약

- **배포:** `main`에 push → GitHub Actions가 Dev Dashboard 앱 Client credentials로 토큰 발급 → `shopify theme push`로 테마 배포.
- **앱:** Dev Dashboard에서 앱 생성 → 버전·스코프(`read_themes`, `write_themes`) 설정 → **Custom distribution** 선택 → 스토어 설치 → Client ID/Secret을 GitHub Secrets에 등록.
- **보안:** Theme Access/레거시 앱 대신, 공식 Dev Dashboard 앱과 24시간 단기 토큰 방식 사용. 장기 토큰을 저장하지 않음.

이 문서는 위 흐름을 기준으로 작성되었으며, Shopify 또는 GitHub 정책 변경 시 일부 단계가 달라질 수 있습니다.

---

## 11. 개발 내역 (Changelog)

테마 커스터마이징 및 배포·운영 관련 변경 사항을 정리합니다.

### 테마 정보·표기

| 항목 | 내용 |
|------|------|
| **테마 표시 이름** | `config/settings_schema.json` → `theme_name`: `"DWSTUDIO - TheBarberSpot"` (Theme library 등에서 표시) |
| **원 개발자** | Shopify (Dawn 기반) |
| **추가 개발·수정·업데이트** | DASOMWEB (`layout/theme.liquid` 상단 주석 및 `theme_author`) |

### 배포·릴리즈

| 항목 | 내용 |
|------|------|
| **트리거** | `main` 브랜치 push 또는 `v*` 태그 push 시 워크플로 실행 |
| **태그 릴리즈** | 태그 푸시 시 `softprops/action-gh-release`로 GitHub Release 자동 생성, 릴리즈 노트 자동 생성 |

### Footer

| 항목 | 내용 |
|------|------|
| **Content layout** | Footer 섹션에서 "Vertical (top to bottom)" 선택 시 미디어쿼리 내 스타일 우선순위 조정으로 정렬이 정상 적용되도록 수정 (`sections/footer.liquid`) |

### Policies and links (footer-utilities)

| 항목 | 내용 |
|------|------|
| **Menu 블록 추가** | "Policies and links"에서 Add block 시 **Menu** 선택 가능하도록 `sections/footer-utilities.liquid` blocks 목록에 `menu` 추가, `max_blocks` 5로 확대 |
| **레이아웃** | 왼쪽: Copyright, 오른쪽: Menu 등 블록 순서로 배치 (2블록 시 1번 왼쪽·2번 오른쪽) |

### Menu 블록 (Policies and links 전용 동작)

| 항목 | 내용 |
|------|------|
| **근본 동작** | Policies and links(`.utilities`) 안의 메뉴는 **Link layout** 설정과 무관하게 항상 **가로 한 줄**로 표시. (`menu--horizontal` 클래스 없어도 적용) |
| **Horizontal alignment** | Left / Center / Right 가 테마 설정대로 정상 적용 (`menu--align-left` / `menu--align-center` / `menu--align-right`) |
| **모바일** | `.utilities .menu` 는 모바일에서도 세로(column)로 전환되지 않고 가로(row) 유지 |

### 수정된 파일 요약

- `.github/workflows/deploy-theme.yml` — 태그 푸시 트리거, GitHub Release 단계
- `config/settings_schema.json` — 테마명
- `layout/theme.liquid` — 개발자 표기 주석
- `sections/footer.liquid` — Content layout 정렬
- `sections/footer-utilities.liquid` — Menu 블록 추가, max_blocks
- `blocks/menu.liquid` — Policies and links 전용 가로·정렬 스타일, 일반 메뉴 정렬 보강
