# The Barber Spot – Shopify Theme

**DWSTUDIO** 테마 v1.0 – The Barber Spot 스토어 전용 (Tinker 기반). **GitHub Actions**로 배포하고, 로컬에서는 CLI로 개발합니다.

- **스토어**: thebarberspot.myshopify.com  
- **에디터**: [테마 에디터](https://admin.shopify.com/store/thebarberspot/themes/153245647037/editor)  
- **배포·설정 상세**: [테마 배포 가이드 (Wiki)](docs/THEME-DEPLOY-WIKI.md)

---

## 배포 (GitHub Actions)

`main` 브랜치에 푸시하면 자동으로 테마(153245647037)에 배포됩니다.

1. **GitHub Environment 설정**  
   저장소 → Settings → Environments → **shopify-thebarberspot** 생성 (없으면).

2. **Environment에 Secrets 추가**  
   해당 Environment의 **Environment secrets**에 다음 4개 설정 (Theme Access 앱·레거시 커스텀 앱 사용 안 함):

   | Secret 이름 | 설명 |
   |-------------|------|
   | `SHOPIFY_FLAG_STORE` | 스토어 주소. 예: `thebarberspot.myshopify.com` |
   | `SHOPIFY_CLIENT_ID` | Dev Dashboard 앱의 Client ID |
   | `SHOPIFY_CLIENT_SECRET` | Dev Dashboard 앱의 Client secret |
   | `SHOPIFY_THEME_ID` | 배포할 테마 ID. 예: `153245647037` |

   **토큰 발급 (Dev Dashboard만 사용)**  
   - **레거시 커스텀 앱**은 2026년 1월 1일부터 새로 만들 수 없음.  
   - **Dev Dashboard**에서 앱을 만들어야 함:  
     [Dev Dashboard](https://dev.shopify.com/dashboard/) → **Create app** → 앱 생성 후 **Configuration**에서 **Admin API** 스코프에 **Theme templates and theme files: Read and write** 추가 → **Install app**으로 본인 스토어에 설치.  
   - 설치 후 **Settings**에서 **Client ID**, **Client secret** 복사 → GitHub Secrets의 `SHOPIFY_CLIENT_ID`, `SHOPIFY_CLIENT_SECRET`에 넣음.  
   - 워크플로가 배포 시마다 위 값으로 24시간 유효 액세스 토큰을 받아 사용함.

---

## Dev Dashboard 앱 만들기 (단계별)

GitHub Actions에서 테마 배포를 위해 필요한 **Client ID / Client secret**은 Dev Dashboard에서 만든 앱에서 가져옵니다.

### 1. Dev Dashboard 접속

- 브라우저에서 **[dev.shopify.com](https://dev.shopify.com/dashboard/)** 접속 후 로그인  
- 왼쪽 메뉴에서 **Apps** 선택

### 2. 앱 생성

- 오른쪽 상단 **Create app** 클릭  
- **Start from Dev Dashboard** 선택  
- 앱 이름 입력 (예: `The Barber Spot Theme Deploy`) 후 **Create** 클릭

### 3. 버전(Version) 만들기

- 앱이 만들어지면 **Versions** 탭으로 이동  
- **Create version** 또는 **Release**로 새 버전 생성  
- **Configuration**에서 다음 설정:

  - **Admin API integration** → **Edit**  
  - **Access scopes**에 테마 권한 추가:
    - `read_themes` (테마 읽기)
    - `write_themes` (테마 쓰기)
  - 필요 시 **Theme templates and theme files** 관련 스코프가 보이면 **Read and write** 선택  
  - **Save** 후 해당 버전을 **Release**로 배포

### 4. 배포 방식(Distribution) 선택 ⚠️

설치 전에 반드시 해야 합니다. 안 하면 "The app developer needs to select a distribution method first" 오류로 설치가 막힙니다.

- **Partners**: [partners.shopify.com](https://partners.shopify.com) → **Apps** → **Theme Push**(또는 해당 앱) 선택  
- 또는 **Dev Dashboard**: [dev.shopify.com](https://dev.shopify.com/dashboard/) → 해당 앱 → **Distribution** / **App distribution** 메뉴 이동  
- **Choose distribution** (또는 "배포 방식 선택") 클릭  
- **Custom distribution** 선택 → **Select**  
  - 이 앱은 본인 스토어(The Barber Spot)용이므로 **Custom**이 맞습니다.  
  - Public은 앱스토어 공개용이라 선택하지 않습니다.  
- Custom 선택 후 스토어 도메인(`thebarberspot.myshopify.com`) 입력하고 **Generate link**로 설치 링크를 만들 수 있습니다(선택).

### 5. 스토어에 앱 설치

- **Install** 버튼 클릭  
- **Select store**에서 **The Barber Spot** 스토어 선택 (또는 사용할 스토어)  
- **Install app** 클릭하여 설치 완료

### 6. Client ID / Client secret 복사

- 왼쪽 메뉴에서 **Settings** 선택  
- **Client credentials** 영역에서:
  - **Client ID** 복사 → GitHub Secret `SHOPIFY_CLIENT_ID`에 저장  
  - **Client secret**의 **Reveal** 클릭 후 복사 → GitHub Secret `SHOPIFY_CLIENT_SECRET`에 저장  

Client secret은 한 번만 보여줄 수 있으니 안전한 곳에 보관하세요.

### 7. GitHub Secrets에 넣기

- GitHub 저장소 → **Settings** → **Environments** → **shopify-thebarberspot**  
- **Environment secrets**에 다음 4개 추가:

  | Name | Value |
  |------|--------|
  | `SHOPIFY_FLAG_STORE` | `thebarberspot.myshopify.com` |
| `SHOPIFY_CLIENT_ID` | 6단계에서 복사한 Client ID |
| `SHOPIFY_CLIENT_SECRET` | 6단계에서 복사한 Client secret |
  | `SHOPIFY_THEME_ID` | `153245647037` |

이후 `main`에 push하면 이 앱 권한으로 액세스 토큰을 받아 테마가 배포됩니다.

3. **배포 방법**  
   - 로컬에서 `git push origin main` 하면 워크플로가 실행되어 테마에 반영됩니다.  
   - 수동 실행: Actions → "Deploy Shopify Theme" → Run workflow.

---

## 로컬 개발 (선택)

미리보기만 할 때:

```bash
npm install -g @shopify/cli @shopify/theme
cd H:\GitHub\DW-STUDIO-The-Barber-Spot
shopify theme dev
```

브라우저에서 스토어 로그인 후, 로컬 변경이 실시간으로 미리보기에 반영됩니다. 배포는 GitHub Actions가 하므로 로컬에서 `theme push`는 필요 없습니다.

---

## 폴더 구조

| 폴더 | 설명 |
|------|------|
| `assets/` | CSS, JS, 이미지 |
| `config/` | 설정 스키마·데이터 |
| `layout/` | theme.liquid 등 |
| `locales/` | 번역 |
| `sections/` | 섹션 |
| `snippets/` | 스니펫 |
| `templates/` | 페이지 템플릿 |
| `blocks/` | 블록 |

