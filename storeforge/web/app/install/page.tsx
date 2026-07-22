"use client";

import { useEffect, useState } from "react";
import Shell from "@/components/Shell";
import InstallRequest from "@/components/InstallRequest";
import { api, ApiError, type Module } from "@/lib/api";

/**
 * 신규 프로젝트용 Dev App 설치 요청문 생성기.
 *
 * 스토어 상세 화면에도 같은 카드가 있지만, 그건 **이미 등록된** 스토어에만 쓸 수 있다.
 * 스토어를 등록하려면 Client ID/Secret 이 있어야 하고, 그 값을 얻으려면 앱을 먼저 만들어야
 * 한다 — 그래서 신규 프로젝트는 여기서 요청문을 뽑는다. 스토어 등록은 자격증명을 받은 뒤에 한다.
 */
export default function InstallPage() {
  const [modules, setModules] = useState<Module[]>([]);
  const [scopes, setScopes] = useState<string[]>([]);
  const [name, setName] = useState("");
  const [domain, setDomain] = useState("");
  const [devStore, setDevStore] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .listModules()
      .then((ms) => {
        setModules(ms);
        // 앱을 만들 때 골라야 할 스코프 = 전 모듈의 합집합. 스토어가 없어도 계산할 수 있다.
        const all = new Set<string>();
        for (const m of ms) {
          for (const s of [...m.required_scopes, ...m.optional_scopes]) all.add(s);
        }
        setScopes([...all].sort());
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : String(err)));
  }, []);

  const normalized = domain.trim().toLowerCase().replace(/^https?:\/\//, "").split("/")[0];
  const shopDomain =
    normalized && !normalized.includes(".")
      ? `${normalized}.myshopify.com`
      : normalized;
  const ready = name.trim().length > 0 && shopDomain.endsWith(".myshopify.com");

  return (
    <Shell>
      <h1>신규 프로젝트 — Dev App 설치 요청</h1>
      <p style={{ color: "var(--muted)", marginTop: -6 }}>
        클라이언트 스토어마다 전용 Shopify 앱을 하나씩 만듭니다. 아래 두 값만 넣으면 Cloud
        Cowork 에 보낼 요청문이 완성됩니다.
      </p>

      {error && <div className="err">{error}</div>}

      <div className="card" style={{ marginBottom: 20 }}>
        <div className="row" style={{ gap: 10 }}>
          <div style={{ flex: 1 }}>
            <label htmlFor="pname">프로젝트명</label>
            <input
              id="pname"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="예) 나누기 스튜디오"
              style={{ width: "100%" }}
            />
          </div>
          <div style={{ flex: 1 }}>
            <label htmlFor="pdomain">스토어 도메인</label>
            <input
              id="pdomain"
              value={domain}
              onChange={(e) => setDomain(e.target.value)}
              placeholder="예) nanugi 또는 nanugi.myshopify.com"
              style={{ width: "100%" }}
            />
          </div>
        </div>
        <label style={{ display: "block", marginTop: 12, cursor: "pointer" }}>
          <input
            type="checkbox"
            checked={devStore}
            onChange={(e) => setDevStore(e.target.checked)}
            style={{ marginRight: 8 }}
          />
          개발용 <strong>Dev store</strong> 다 (신규 생성 단계 포함)
        </label>
        <p style={{ color: "var(--muted)", fontSize: 12, marginBottom: 0 }}>
          Dev store 는 고객 이전이 불가능한 타입이라 커스텀 앱이 정상 설치됩니다. 반대로{" "}
          <strong>Client transfer store 에는 커스텀 앱을 설치할 수 없습니다</strong> — 고객 스토어는
          이전(Transfer)이 끝난 뒤에 이 요청을 보내세요.
        </p>

        {domain && !ready && (
          <p style={{ color: "var(--muted)", fontSize: 12, marginBottom: 0 }}>
            프로젝트명과 <span className="mono">*.myshopify.com</span> 도메인이 모두 필요합니다.
          </p>
        )}
      </div>

      {ready ? (
        <InstallRequest
          projectName={name.trim()}
          shopDomain={shopDomain}
          scopes={scopes}
          modules={modules}
          createDevStore={devStore}
        />
      ) : (
        <p style={{ color: "var(--muted)" }}>
          값을 입력하면 요청문이 여기에 생성됩니다.
        </p>
      )}
    </Shell>
  );
}
