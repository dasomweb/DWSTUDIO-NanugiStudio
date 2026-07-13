"use client";

import type { AuthType, Credentials } from "@/lib/api";

/** 스토어 자격증명 입력란. 등록 화면과 교체 화면이 같이 쓴다. */
export default function CredentialsFields({
  value,
  onChange,
  idPrefix,
}: {
  value: Credentials;
  onChange: (next: Credentials) => void;
  idPrefix: string;
}) {
  const set = (patch: Partial<Credentials>) => onChange({ ...value, ...patch });

  const pickMode = (mode: AuthType) =>
    // 방식을 바꾸면 반대쪽 입력값은 버린다 — 잘못된 조합이 서버로 나가지 않게.
    onChange({ auth_type: mode });

  return (
    <>
      <div style={{ marginBottom: 12 }}>
        <label>인증 방식</label>
        <div className="row" style={{ gap: 8 }}>
          <button
            type="button"
            className={value.auth_type === "client_credentials" ? "" : "ghost"}
            onClick={() => pickMode("client_credentials")}
          >
            Client ID / Secret
          </button>
          <button
            type="button"
            className={value.auth_type === "token" ? "" : "ghost"}
            onClick={() => pickMode("token")}
          >
            액세스 토큰
          </button>
        </div>
      </div>

      {value.auth_type === "client_credentials" ? (
        <>
          <div className="note" style={{ marginBottom: 12 }}>
            앱의 <span className="mono">client_id</span> /{" "}
            <span className="mono">client_secret</span> 으로 요청할 때마다 짧은 수명의 토큰을
            발급받습니다. 영구 토큰을 보관하지 않으므로 안전하고, 나누기의 기존 테마 배포
            워크플로와 같은 방식입니다. <strong>권장.</strong>
          </div>
          <div className="grid two" style={{ marginBottom: 12 }}>
            <div>
              <label htmlFor={`${idPrefix}-cid`}>Client ID</label>
              <input
                id={`${idPrefix}-cid`}
                className="mono"
                autoComplete="off"
                value={value.client_id ?? ""}
                onChange={(e) => set({ client_id: e.target.value })}
                required
              />
            </div>
            <div>
              <label htmlFor={`${idPrefix}-csec`}>Client Secret</label>
              <input
                id={`${idPrefix}-csec`}
                type="password"
                className="mono"
                autoComplete="new-password"
                value={value.client_secret ?? ""}
                onChange={(e) => set({ client_secret: e.target.value })}
                required
              />
            </div>
          </div>
        </>
      ) : (
        <>
          <div className="note" style={{ marginBottom: 12 }}>
            커스텀 앱 설치 시 한 번만 표시되는 영구 Admin API 토큰입니다. client_credentials 를
            쓸 수 없는 앱을 위한 대안입니다.
          </div>
          <div style={{ marginBottom: 12 }}>
            <label htmlFor={`${idPrefix}-tok`}>Admin API 액세스 토큰</label>
            <input
              id={`${idPrefix}-tok`}
              type="password"
              className="mono"
              autoComplete="new-password"
              placeholder="shpat_…"
              value={value.access_token ?? ""}
              onChange={(e) => set({ access_token: e.target.value })}
              required
            />
          </div>
        </>
      )}

      <div className="note" style={{ marginBottom: 14 }}>
        모든 비밀값은 <strong>Fernet 으로 암호화되어 저장</strong>되며, 이후 어떤 응답에도
        실리지 않습니다. 필요한 스코프:{" "}
        <span className="mono">write_metafields</span> (필수),{" "}
        <span className="mono">read_products</span> (권장)
      </div>
    </>
  );
}
