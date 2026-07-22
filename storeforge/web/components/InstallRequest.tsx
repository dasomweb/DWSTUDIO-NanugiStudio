"use client";

import { useMemo, useState } from "react";
import type { Module } from "@/lib/api";

/**
 * Cloud Cowork 에 보낼 "Dev App 생성·설치 요청문"을 스토어별로 만들어 준다.
 *
 * 설치는 항상 Cloud Cowork 가 대행하므로, 사람이 절차를 외우는 대신 이 텍스트를 통째로
 * 복사해 전달한다. 스토어 도메인·앱 이름·스코프가 이미 채워져 있어 손댈 곳이 없다.
 *
 * 스코프는 화면에서 켠 모듈이 아니라 **전 모듈의 합집합(install_scopes)** 을 쓴다.
 * 앱 스코프를 나중에 늘리려면 새 버전 Release + 앱 재설치가 필요하기 때문에,
 * 지금 안 쓰는 모듈이라도 처음부터 넣어 두는 편이 낫다.
 */
export default function InstallRequest({
  projectName,
  shopDomain,
  scopes,
  modules,
  createDevStore = false,
}: {
  projectName: string;
  shopDomain: string;
  scopes: string[];
  modules: Module[];
  /** 개발용 스토어를 새로 만드는 요청까지 포함할지. 고객 스토어에는 켜지 않는다. */
  createDevStore?: boolean;
}) {
  const [copied, setCopied] = useState(false);

  const text = useMemo(
    () => buildRequest(projectName, shopDomain, scopes, modules, createDevStore),
    [projectName, shopDomain, scopes, modules, createDevStore]
  );

  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  }

  return (
    <div className="card" style={{ marginBottom: 20 }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          marginBottom: 10,
        }}
      >
        <h2 style={{ margin: 0, flex: 1 }}>Dev App 설치 요청문 (Cloud Cowork)</h2>
        <button onClick={copy}>{copied ? "복사됨 ✓" : "복사"}</button>
      </div>

      <p style={{ color: "var(--muted)", fontSize: 13, marginTop: 0 }}>
        이 스토어 전용 Shopify Dev App 을 만들고 설치하는 요청문입니다. 그대로 복사해 Cloud
        Cowork 에 전달하세요. Custom distribution 앱은 <strong>스토어 한 곳에만</strong> 설치할 수
        있으므로 <strong>프로젝트마다 앱을 하나씩</strong> 만듭니다.
      </p>

      <textarea
        readOnly
        value={text}
        rows={26}
        className="mono"
        style={{ width: "100%", fontSize: 12, lineHeight: 1.5 }}
        onFocus={(e) => e.currentTarget.select()}
      />
    </div>
  );
}

export function buildRequest(
  projectName: string,
  shopDomain: string,
  scopes: string[],
  modules: Module[],
  createDevStore = false
): string {
  const appName = `DWSTUDIO Suite — ${projectName}`;

  // 어떤 스코프가 왜 필요한지 같이 적어준다. 목록만 주면 나중에 누가 "이거 왜 있지?" 하고 뺀다.
  const why: Record<string, string> = {};
  for (const m of modules) {
    for (const s of [...m.required_scopes, ...m.optional_scopes]) {
      why[s] = why[s] ? `${why[s]}, ${m.name}` : m.name;
    }
  }

  return `[Cloud Cowork 요청] Shopify Dev App 생성 및 설치

■ 프로젝트
  스토어      : ${shopDomain}
  앱 이름     : ${appName}
  배포 방식   : Custom distribution (이 스토어 전용 / 승인 불요)

■ ⚠️ 시작 전 반드시 확인 (여기서 막히면 뒤 단계가 전부 무의미합니다)
${
  createDevStore
    ? `
  이 요청은 **개발용 Dev store** 대상입니다. Dev store 는 고객 이전이 불가능한 타입이라
  (= transfer-disabled) 커스텀 앱이 정상 설치됩니다.

  ▸ 반드시 **Dev store** 로 만들어 주세요. **"Client transfer store" 로 만들면 안 됩니다** —
    그 타입에는 커스텀 앱을 설치할 수 없습니다.
`
    : `
  Dev Dashboard → Stores 에서 ${shopDomain} 의 타입을 확인해 주세요.

  ▸ "Client transfer" 타입이거나 상태가 "In development" 이면 → **작업을 중단하고 알려주세요.**
    client transfer 스토어가 파트너 조직에 남아 있는 동안에는 무료 앱·파트너 친화 앱만 설치할 수
    있고, **커스텀 앱은 설치할 수 없습니다.** 설치를 시도하면 install link 를 몇 번 새로 뽑아도
    "The installation link for this app is invalid" 가 반복됩니다. 링크나 로그인 세션 문제가
    아니라 구조적 제약입니다. → **고객에게 스토어를 Transfer 한 뒤에 이 요청을 진행합니다.**

  ▸ 정식 스토어(유료 플랜) 또는 Dev store(transfer-disabled)이면 → 아래 순서대로 진행합니다.
`
}
  ▸ 절대 하지 말 것: \`shopify app dev\` 로 우회 설치.
    고객 이전용 스토어에 커스텀/draft 앱을 설치하면 **transfer 가 영구 비활성화**되어 고객에게
    스토어를 넘길 수 없게 됩니다. Shopify CLI 는 이 변환을 경고 없이 수행합니다 (Shopify/cli#3946).

■ 작업 순서
${
  createDevStore
    ? `
0) 개발 스토어 생성 (이미 있으면 건너뜁니다)
   Dev Dashboard → Stores → Create store
   - 스토어 타입: **Dev store** (Client transfer store 아님)
   - 스토어 도메인: ${shopDomain}
   - 플랜: 아무거나 (개발 스토어는 실결제가 없습니다)
`
    : ""
}

1) 앱 생성
   https://dev.shopify.com/dashboard → Apps → Create app → Start from Dev Dashboard
   앱 이름: ${appName}

   ※ Shopify 관리자(admin.shopify.com)의 "앱 개발" 메뉴로 만드는 레거시 커스텀 앱은
     2026-01-01 부터 신규 생성이 불가능합니다. 반드시 Dev Dashboard 에서 만들어 주세요.

2) 버전 생성 → Admin API 스코프 지정
   Versions → Create version → Configuration → Admin API integration
   아래 스코프를 모두 체크:

${scopes.map((s) => `     - ${s}${why[s] ? `   (${why[s]})` : ""}`).join("\n")}

   ※ write_metafields 는 현재 존재하지 않는 스코프입니다.
     입력하면 "Contains invalid scopes" 오류가 납니다. 넣지 마세요.

3) Release
   버전을 Release 해야 스코프가 실제로 적용됩니다. (저장만 하면 반영되지 않습니다)

4) Distribution
   Distribution → Choose distribution → Custom distribution
   대상 스토어: ${shopDomain}
   → Install link 생성
   ※ 한 번 고르면 되돌릴 수 없습니다. Public 을 고르지 마세요.

5) 설치
   생성된 Install link 를 ${shopDomain} 관리자 계정으로 로그인된 브라우저에서 엽니다.
   (파트너/개발 계정으로 로그인된 창에서 열면 안 됩니다 — 시크릿 창을 사용하세요)
   설치 후 App URL(플레이스홀더)로 리다이렉트되는 것은 정상입니다.

6) 자격증명 전달
   Settings → Client credentials 에서 아래 두 값을 확보해 전달해 주세요.
     - Client ID
     - Client secret  (Reveal 클릭 후 복사. 최초 1회만 노출됩니다 — 안전한 경로로 전달)

■ 전달받은 값의 사용처
  - StoreForge 관리자 페이지 → ${projectName} → 자격증명 교체 → client_credentials 방식
  - GitHub Actions 테마 배포 → Environment Secrets
        SHOPIFY_CLIENT_ID / SHOPIFY_CLIENT_SECRET / SHOPIFY_FLAG_STORE / SHOPIFY_THEME_ID

■ 참고
  - 영구 액세스 토큰(shpat_…)은 필요 없습니다. client_credentials 로 매번 24시간 토큰을 받습니다.
  - 스코프를 나중에 바꾸려면 새 버전 Release + 앱 재설치가 필요합니다.
    그래서 지금 당장 쓰지 않는 모듈의 스코프도 위 목록에 포함해 두었습니다.
`;
}
