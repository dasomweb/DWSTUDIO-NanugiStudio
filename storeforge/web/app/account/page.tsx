"use client";

import { useEffect, useState } from "react";
import Shell from "@/components/Shell";
import { api, ApiError, getUser, setSession, type User } from "@/lib/api";

const ROLE_KO: Record<string, string> = {
  superadmin: "슈퍼어드민",
  admin: "어드민",
  owner: "오너",
};

export default function AccountPage() {
  const [user, setUser] = useState<User | null>(null);

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [profileBusy, setProfileBusy] = useState(false);

  const [currentPw, setCurrentPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [confirmPw, setConfirmPw] = useState("");
  const [pwBusy, setPwBusy] = useState(false);

  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);

  useEffect(() => {
    const u = getUser();
    if (u) {
      setUser(u);
      setName(u.name ?? "");
      setEmail(u.email);
    }
  }, []);

  if (!user) return <Shell>{null}</Shell>;

  async function saveProfile(e: React.FormEvent) {
    e.preventDefault();
    setProfileBusy(true);
    setError(null);
    setOk(null);
    try {
      const updated = await api.updateProfile({ name, email });
      // 사이드바가 읽는 세션 캐시도 갱신한다.
      const token = window.localStorage.getItem("storeforge.token");
      if (token) setSession(token, updated);
      setUser(updated);
      setOk("프로필을 저장했습니다.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setProfileBusy(false);
    }
  }

  async function savePassword(e: React.FormEvent) {
    e.preventDefault();
    if (newPw !== confirmPw) {
      setError("새 비밀번호가 서로 다릅니다.");
      return;
    }
    setPwBusy(true);
    setError(null);
    setOk(null);
    try {
      const res = await api.changePassword(currentPw, newPw);
      // 비밀번호를 바꾸면 새 토큰이 나온다. 세션을 갈아끼워야 로그아웃되지 않는다.
      setSession(res.access_token, res.user);
      setUser(res.user);
      setCurrentPw("");
      setNewPw("");
      setConfirmPw("");
      setOk("비밀번호를 변경했습니다. 다음 로그인부터 새 비밀번호를 쓰세요.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setPwBusy(false);
    }
  }

  return (
    <Shell>
      <h1>계정</h1>
      <p className="sub">내 프로필과 비밀번호를 변경합니다.</p>

      {error && <div className="err">{error}</div>}
      {ok && (
        <div className="note" style={{ marginBottom: 16, color: "var(--ok)" }}>
          {ok}
        </div>
      )}

      <form className="card" onSubmit={saveProfile}>
        <h2>프로필</h2>
        <div className="grid two" style={{ marginBottom: 14 }}>
          <div>
            <label htmlFor="a-name">이름</label>
            <input id="a-name" value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div>
            <label htmlFor="a-email">이메일 (로그인 아이디)</label>
            <input
              id="a-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
        </div>
        <div className="row">
          <span className="pill">{ROLE_KO[user.role] ?? user.role}</span>
          <span className="sub" style={{ margin: 0, fontSize: 12 }}>
            역할은 슈퍼어드민만 변경할 수 있습니다.
          </span>
        </div>
        <div className="row" style={{ marginTop: 14 }}>
          <button type="submit" disabled={profileBusy}>
            {profileBusy ? "저장 중…" : "프로필 저장"}
          </button>
        </div>
      </form>

      <form className="card" onSubmit={savePassword}>
        <h2>비밀번호 변경</h2>
        <div className="note" style={{ marginBottom: 14 }}>
          최초 계정은 배포 시 자동 생성된 임시 비밀번호를 씁니다.{" "}
          <strong>지금 바꾸고 Railway 의 임시 비밀번호는 폐기하세요.</strong>
        </div>

        <div style={{ marginBottom: 12, maxWidth: 420 }}>
          <label htmlFor="a-cur">현재 비밀번호</label>
          <input
            id="a-cur"
            type="password"
            autoComplete="current-password"
            value={currentPw}
            onChange={(e) => setCurrentPw(e.target.value)}
            required
          />
        </div>
        <div className="grid two" style={{ marginBottom: 14 }}>
          <div>
            <label htmlFor="a-new">새 비밀번호 (8자 이상)</label>
            <input
              id="a-new"
              type="password"
              autoComplete="new-password"
              minLength={8}
              value={newPw}
              onChange={(e) => setNewPw(e.target.value)}
              required
            />
          </div>
          <div>
            <label htmlFor="a-new2">새 비밀번호 확인</label>
            <input
              id="a-new2"
              type="password"
              autoComplete="new-password"
              minLength={8}
              value={confirmPw}
              onChange={(e) => setConfirmPw(e.target.value)}
              required
            />
          </div>
        </div>
        <button type="submit" disabled={pwBusy}>
          {pwBusy ? "변경 중…" : "비밀번호 변경"}
        </button>
      </form>
    </Shell>
  );
}
