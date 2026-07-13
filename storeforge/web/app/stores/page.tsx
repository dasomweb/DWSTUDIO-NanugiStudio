"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import Shell from "@/components/Shell";
import { api, ApiError, getUser, type Store } from "@/lib/api";

export default function StoresPage() {
  const [stores, setStores] = useState<Store[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [adding, setAdding] = useState(false);
  const [busy, setBusy] = useState(false);

  const [name, setName] = useState("");
  const [domain, setDomain] = useState("");
  const [token, setToken] = useState("");

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
      await api.createStore({ name, shop_domain: domain, access_token: token });
      setName("");
      setDomain("");
      setToken("");
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
      <p className="sub">연동된 Shopify 스토어. 온보딩은 여기서 스토어를 골라 실행합니다.</p>

      {error && <div className="err">{error}</div>}

      {canAdd && !adding && (
        <button onClick={() => setAdding(true)} style={{ marginBottom: 16 }}>
          + 스토어 연동
        </button>
      )}

      {adding && (
        <form className="card" onSubmit={addStore}>
          <h2>Shopify 스토어 연동</h2>
          <div className="note" style={{ marginBottom: 14 }}>
            Phase 1 은 <strong>커스텀 앱</strong> 방식입니다. Shopify 관리자 →{" "}
            <span className="mono">설정 → 앱 및 판매 채널 → 앱 개발</span> 에서 앱을 만들고,
            <span className="mono"> write_metafields</span> 스코프를 켠 뒤 발급되는 Admin API
            액세스 토큰(<span className="mono">shpat_…</span>)을 붙여넣으세요. 토큰은 암호화해
            저장되며 다시 보여주지 않습니다.
          </div>

          <div className="grid two" style={{ marginBottom: 12 }}>
            <div>
              <label htmlFor="s-name">표시 이름</label>
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
                value={domain}
                onChange={(e) => setDomain(e.target.value)}
                placeholder="nanugi.myshopify.com"
                required
              />
            </div>
          </div>

          <div style={{ marginBottom: 14 }}>
            <label htmlFor="s-token">Admin API 액세스 토큰</label>
            <input
              id="s-token"
              type="password"
              className="mono"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              placeholder="shpat_…"
              required
            />
          </div>

          <div className="row">
            <button type="submit" disabled={busy}>
              {busy ? "연결 확인 중…" : "연동하고 연결 테스트"}
            </button>
            <button type="button" className="ghost" onClick={() => setAdding(false)}>
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
                <th>이름</th>
                <th>도메인</th>
                <th>상태</th>
                <th>플랜</th>
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
                  <td>
                    {s.connected ? (
                      <span className="pill ok">연결됨</span>
                    ) : (
                      <span className="pill bad" title={s.last_error ?? ""}>
                        연결 안 됨
                      </span>
                    )}
                  </td>
                  <td style={{ color: "var(--muted)" }}>{s.shop_plan ?? "—"}</td>
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
          <strong>연결 실패 사유</strong>
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
