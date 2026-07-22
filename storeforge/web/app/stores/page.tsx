"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import Shell from "@/components/Shell";
import CredentialsFields from "@/components/CredentialsFields";
import { api, ApiError, getUser, type Credentials, type Store } from "@/lib/api";

const EMPTY_CREDS: Credentials = { auth_type: "client_credentials" };

/** 부여된 스코프 대비 필수 스코프 충족 여부. */
function ScopeBadge({ store }: { store: Store }) {
  if (!store.connected) return <span style={{ color: "var(--muted)" }}>—</span>;
  if (store.granted_scopes.length === 0)
    return <span className="pill">스코프 확인 불가</span>;
  if (store.missing_scopes.length > 0)
    return (
      <span className="pill bad" title={`누락: ${store.missing_scopes.join(", ")}`}>
        {store.missing_scopes.join(", ")} 없음
      </span>
    );
  return <span className="pill ok">스코프 충족</span>;
}

export default function StoresPage() {
  const [stores, setStores] = useState<Store[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [adding, setAdding] = useState(false);
  const [busy, setBusy] = useState(false);

  const [name, setName] = useState("");
  const [domain, setDomain] = useState("");
  const [creds, setCreds] = useState<Credentials>(EMPTY_CREDS);

  const canAdd = ["superadmin", "admin"].includes(getUser()?.role ?? "");

  const load = useCallback(async () => {
    try {
      setStores(await api.listStores());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function addStore(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.createStore({ name, shop_domain: domain, ...creds });
      setName("");
      setDomain("");
      setCreds(EMPTY_CREDS);
      setAdding(false);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function test(id: number) {
    setError(null);
    try {
      await api.testStore(id);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    }
  }

  return (
    <Shell>
      <h1>스토어</h1>
      <p className="sub">
        연동된 Shopify 스토어. 프로젝트마다 자격증명을 따로 갖습니다. 온보딩은 여기서 스토어를
        골라 실행합니다.
      </p>

      {error && <div className="err">{error}</div>}

      {canAdd && !adding && (
        <button onClick={() => setAdding(true)} style={{ marginBottom: 16 }}>
          + 스토어 연동
        </button>
      )}

      {adding && (
        <form className="card" onSubmit={addStore}>
          <h2>Shopify 스토어 연동</h2>

          <div className="grid two" style={{ marginBottom: 12 }}>
            <div>
              <label htmlFor="s-name">표시 이름 (프로젝트명)</label>
              <input
                id="s-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="나누기 스튜디오"
                required
              />
            </div>
            <div>
              <label htmlFor="s-domain">스토어 도메인</label>
              <input
                id="s-domain"
                className="mono"
                value={domain}
                onChange={(e) => setDomain(e.target.value)}
                placeholder="nanugi.myshopify.com"
                required
              />
            </div>
          </div>

          <CredentialsFields value={creds} onChange={setCreds} idPrefix="new" />

          <div className="row">
            <button type="submit" disabled={busy}>
              {busy ? "연결 확인 중…" : "연동하고 연결 테스트"}
            </button>
            <button
              type="button"
              className="ghost"
              onClick={() => {
                setAdding(false);
                setCreds(EMPTY_CREDS);
              }}
            >
              취소
            </button>
          </div>
        </form>
      )}

      <div className="card">
        {loading ? (
          <p className="sub" style={{ margin: 0 }}>
            불러오는 중…
          </p>
        ) : stores.length === 0 ? (
          <p className="sub" style={{ margin: 0 }}>
            연동된 스토어가 없습니다.
            {!canAdd && " 관리자에게 스토어 배정을 요청하세요."}
          </p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>프로젝트</th>
                <th>도메인</th>
                <th>인증</th>
                <th>연결</th>
                <th>스코프</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {stores.map((s) => (
                <tr key={s.id}>
                  <td>
                    <Link href={`/stores/${s.id}`} style={{ fontWeight: 600 }}>
                      {s.name}
                    </Link>
                  </td>
                  <td className="mono">{s.shop_domain}</td>
                  <td style={{ color: "var(--muted)", fontSize: 12 }}>
                    {s.auth_type === "client_credentials" ? "Client ID/Secret" : "액세스 토큰"}
                  </td>
                  <td>
                    {s.connected ? (
                      <span className="pill ok">연결됨</span>
                    ) : (
                      <span className="pill bad">연결 안 됨</span>
                    )}
                  </td>
                  <td>
                    <ScopeBadge store={s} />
                  </td>
                  <td style={{ textAlign: "right" }}>
                    <button className="ghost" onClick={() => test(s.id)}>
                      연결 테스트
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {stores.some((s) => !s.connected && s.last_error) && (
        <div className="note">
          <strong style={{ color: "var(--text)" }}>연결 실패 사유</strong>
          <ul style={{ margin: "8px 0 0", paddingLeft: 18 }}>
            {stores
              .filter((s) => !s.connected && s.last_error)
              .map((s) => (
                <li key={s.id}>
                  <span className="mono">{s.shop_domain}</span> — {s.last_error}
                </li>
              ))}
          </ul>
        </div>
      )}
    </Shell>
  );
}
