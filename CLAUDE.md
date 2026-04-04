# CLAUDE.md — DWSTUDIO-NanugiStudio

Claude Code가 이 프로젝트에서 작업할 때 항상 참조하는 문서입니다.

---

## 프로젝트 개요

- **테마**: DWSTUDIO v1.0 (Tinker/Dawn 기반 커스텀 Shopify 테마)
- **스토어**: nanugi.myshopify.com
- **테마 ID**: 158825414873
- **테마 에디터**: https://admin.shopify.com/store/nanugi/themes/158825414873/editor

---

## 배포 전략 (이중 운영)

이 프로젝트는 **GitHub Actions 배포 + Shopify 에디터 자동 동기화**를 병행합니다.

### 코드 변경 (Liquid, CSS, JS)
- GitHub에서 작업 → `main` 푸시 → GitHub Actions가 자동 배포
- 워크플로: `.github/workflows/deploy-theme.yml`
- Environment: `shopify-nanugi`

### 콘텐츠/설정 변경 (테마 에디터)
- 클라이언트/디자이너가 Shopify 테마 에디터에서 직접 수정
- 변경 사항이 "Update from Shopify for theme DWSTUDIO-NanugiStudio/main" 커밋으로 자동 동기화됨
- 주로 변경되는 파일: `config/settings_data.json`, `templates/*.json`, `sections/*-group.json`

### 히스토리 관리 규칙

1. **Shopify 동기화 커밋은 건드리지 않는다** — 자동 생성되는 커밋이므로 수정/squash 하지 않음
2. **개발 커밋만 필터링할 때**: `git log --invert-grep --grep="Update from Shopify"`
3. **커밋 메시지 컨벤션** (개발자 커밋):
   - `feat:` 새 기능 추가
   - `fix:` 버그 수정
   - `style:` CSS/UI 변경
   - `refactor:` 코드 리팩토링
   - `chore:` 배포, 설정 변경 등
   - `docs:` 문서 수정
   - 예: `feat: 상품 페이지에 리뷰 섹션 추가`
4. **버전 태그**: `v{major}.{minor}.{patch}` (예: v1.0.15)
5. **릴리즈**: 태그 푸시 시 GitHub Release 자동 생성

---

## 폴더 구조

| 폴더 | 용도 | 비고 |
|------|------|------|
| `assets/` | CSS, JS, SVG, 이미지 | 77개 JS 모듈, base.css |
| `blocks/` | 블록 컴포넌트 | `_` 프리픽스, 96개 |
| `config/` | 테마 설정 | settings_schema.json, settings_data.json |
| `layout/` | 레이아웃 | theme.liquid, password.liquid, ecom.liquid |
| `locales/` | 번역 파일 | 54개 언어 |
| `sections/` | 섹션 | 44개 (42 liquid + 2 JSON) |
| `snippets/` | 스니펫 | 112개 재사용 컴포넌트 |
| `templates/` | 페이지 템플릿 | 15개 (JSON + Liquid) |
| `docs/` | 프로젝트 문서 | 배포 가이드, 검증 로그 |

---

## 기술 스택

- **테마 엔진**: Shopify Liquid
- **CSS**: 커스텀 CSS (CSS Custom Properties 활용, 컬러 스킴 시스템)
- **JS**: Vanilla JS 모듈 (Web Components 패턴)
- **서드파티**: eComposer 페이지 빌더 통합 (19개 훅 스니펫)
- **폰트**: Bebas Neue (헤딩), Oswald (서브헤딩), Roboto (본문)
- **브랜드 컬러**: #000000 (프라이머리), #82a31a (세컨더리), #c3cca6 (액센트)

---

## 개발 시 주의사항

1. **config/settings_data.json** — 테마 에디터가 관리하므로 직접 수정 지양. 수정 시 에디터 동기화와 충돌 가능
2. **templates/*.json** — 에디터에서 섹션 배치를 변경하면 자동 업데이트됨. 수동 수정 시 주의
3. **sections/*-group.json** — 헤더/푸터 그룹 설정. 에디터 동기화 대상
4. **settings_schema.json** — 테마 설정 스키마 정의. 이건 코드에서만 수정
5. **.shopifyignore** — `*.md` 파일은 Shopify에 배포되지 않음 (docs, CLAUDE.md 등 안전)
6. **eComposer 스니펫** (`snippets/ecom-*.liquid`) — 서드파티 훅이므로 함부로 수정하지 않음

---

## 로컬 개발

```bash
npm install -g @shopify/cli @shopify/theme
shopify theme dev
```

로컬 미리보기 전용. 배포는 반드시 GitHub Actions로.

---

## 유용한 명령어

```bash
# 개발 커밋만 보기 (Shopify 동기화 제외)
git log --invert-grep --grep="Update from Shopify"

# 특정 파일의 개발 변경 이력만 보기
git log --invert-grep --grep="Update from Shopify" -- sections/footer.liquid

# 최근 릴리즈 확인
git tag -l | sort -V | tail -5
```
