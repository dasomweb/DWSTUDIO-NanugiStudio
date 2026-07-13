"use client";

import { useCallback, useEffect, useState } from "react";
import Shell from "@/components/Shell";
import { api, ApiError, type Role, type Store, type User } from "@/lib/api";

const ROLE_KO: Record<Role, string> = {
  superadmin: "슈퍼어드민",
  admin: "어드민",
  owner: "오너",
};

const ROLE_DESC: Record<Role, string> = {
  superadmin: "전 스토어 + 사용자 관리",
  admin: "배정된 스토어 관리, 스토어 연동 가능",
  owner: "배정된 자기 스토어만",
};

export default function UsersPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [stores, setStores] = useState<Store[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [okMsg, setOkMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [adding, setAdding] = useState(false);

  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<Role>("owner");
  const [storeIds, setStoreIds] = useState<number[]>([]);

  const load = useCallback(async () => {
    try {
      const [u, s] = await Promise.all([api.listUsers(), api.listStores()]);
      setUsers(u);
      setStores(s);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.createUser({ email, name, password, role, store_ids: storeIds });
      setEmail("");
      setName("");
      setPassword("");
      setStoreIds([]);
      setAdding(false);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function deactivate(id: number) {
    setError(null);
    try {
      await api.deactivateUser(id);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    }
  }

  async function resetPassword(u: User) {
    const pw = window.prompt(
      `${u.email} 의 새 비밀번호를 입력하세요 (8자 이상).\n입력한 값을 본인에게 직접 전달해야 합니다.`,
    );
    if (!pw) return;
    setError(null);
    setOkMsg(null);
    try {
      await api.resetUserPassword(u.id, pw);
      setOkMsg(`${u.email} 의 비밀번호를 재설정했습니다.`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    }
  }

  return (
    <Shell>
      <h1>사용자</h1>
      <p className="sub">슈퍼어드민 전용. 역할과 스토어 배정을 여기서 관리합니다.</p>

      {error && <div className="err">{error}</div>}
      {okMsg && (
        <div className="note" style={{ marginBottom: 16, color: "var(--ok)" }}>
          {okMsg}
        </div>
      )}

      {!adding && (
        <button onClick={() => setAdding(true)} style={{ marginBottom: 16 }}>
          + 사용자 추가
        </button>
      )}

      {adding && (
        <form className="card" onSubmit={create}>
          <h2>사용자 추가</h2>
          <div className="grid two" style={{ marginBottom: 12 }}>
            <div>
              <label htmlFor="u-email">이메일</label>
              <input
                id="u-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
            <div>
              <label htmlFor="u-name">이름</label>
              <input id="u-name" value={name} onChange={(e) => setName(e.target.value)} />
            </div>
          </div>

          <div className="grid two" style={{ marginBottom: 12 }}>
            <div>
              <label htmlFor="u-pw">비밀번호 (8자 이상)</label>
              <input
                id="u-pw"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                minLength={8}
                required
              />
            </div>
            <div>
              <label htmlFor="u-role">역할</label>
              <select
                id="u-role"
                value={role}
                onChange={(e) => setRole(e.target.value as Role)}
              >
                {(Object.keys(ROLE_KO) as Role[]).map((r) => (
                  <option key={r} value={r}>
                    {ROLE_KO[r]} — {ROLE_DESC[r]}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {role !== "superadmin" && (
            <div style={{ marginBottom: 14 }}>
              <label>스토어 배정</label>
              {stores.length === 0 ? (
                <p className="sub" style={{ margin: 0, fontSize: 12 }}>
                  연동된 스토어가 없습니다.
                </p>
              ) : (
                <div className="row">
                  {stores.map((s) => (
                    <label
                      key={s.id}
                      className="pill"
                      style={{ cursor: "pointer", color: "var(--text)" }}
                    >
                      <input
                        type="checkbox"
                        style={{ width: 14, height: 14 }}
                        checked={storeIds.includes(s.id)}
                        onChange={(e) =>
                          setStoreIds((prev) =>
                            e.target.checked
                              ? [...prev, s.id]
                              : prev.filter((x) => x !== s.id),
                          )
                        }
                      />
                      {s.name}
                    </label>
                  ))}
                </div>
              )}
            </div>
          )}

          <div className="row">
            <button type="submit" disabled={busy}>
              {busy ? "생성 중…" : "생성"}
            </button>
            <button type="button" className="ghost" onClick={() => setAdding(false)}>
              취소
            </button>
          </div>
        </form>
      )}

      <div className="card">
        <table>
          <thead>
            <tr>
              <th>이메일</th>
              <th>이름</th>
              <th>역할</th>
              <th>상태</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id}>
                <td className="mono">{u.email}</td>
                <td>{u.name || "—"}</td>
                <td>
                  <span className="pill">{ROLE_KO[u.role]}</span>
                </td>
                <td>
                  {u.is_active ? (
                    <span className="pill ok">활성</span>
                  ) : (
                    <span className="pill bad">비활성</span>
                  )}
                </td>
                <td style={{ textAlign: "right" }}>
                  <div className="row" style={{ justifyContent: "flex-end" }}>
                    <button className="ghost" onClick={() => resetPassword(u)}>
                      비밀번호 재설정
                    </button>
                    {u.is_active && u.role !== "superadmin" && (
                      <button className="danger" onClick={() => deactivate(u.id)}>
                        비활성화
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Shell>
  );
}
