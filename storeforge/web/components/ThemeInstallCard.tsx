"use client";

import { useEffect, useState } from "react";
import { api, ApiError, type Store, type ThemeInstall } from "@/lib/api";

/**
 * 소스 테마 설치 카드 (기획안 §6.3).
 *
 * GitHub 릴리즈의 theme.zip 을 themeCreate 로 넣어 이 스토어에 **GitHub 미연동 테마**를
 * 만든다. 색상은 여기서 정하지 않는다 — 설치 후 아래의 브랜드 주입(축①)이 metafield 로
 * 입힌다. 그래서 zip 은 모든 스토어에 동일하다.
 */
export default function ThemeInstallCard({ store }: { store: Store }) {
  const [zipUrl, setZipUrl] = useState("");
  const [publish, setPublish] = useState(true);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<ThemeInstall | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.themeSource().then((s) => setZipUrl(s.zip_url)).catch(() => {});
  }, []);

  const scopeMissing =
    store.granted_scopes.length > 0 && !store.granted_scopes.includes("write_themes");

  async function install() {
    setBusy(true);
    setError("");
    setResult(null);
    try {
      setResult(await api.installTheme(store.id, publish));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card" style={{ marginBottom: 20 }}>
      <h2 style={{ marginTop: 0 }}>테마 설치</h2>
      <p style={{ color: "var(--muted)", fontSize: 13, marginTop: 0 }}>
        소스 테마(릴리즈 zip)를 이 스토어에 <strong>GitHub 미연동 테마</strong>로 설치합니다.
        기존 테마는 삭제되지 않으므로 잘못돼도 되돌릴 수 있습니다. 색상·폰트는 설치 후 아래
        브랜드 주입이 입힙니다.
      </p>

      <div className="mono" style={{ fontSize: 12, color: "var(--muted)", marginBottom: 10 }}>
        {zipUrl || "zip URL 불러오는 중…"}
      </div>

      {scopeMissing && (
        <div className="err">
          <span className="mono">write_themes</span> 스코프가 없어 설치할 수 없습니다.
        </div>
      )}
      {error && <div className="err">{error}</div>}
      {result && (
        <div className="ok">
          설치 완료 — <strong>{result.theme_name}</strong>
          {result.published ? " (라이브로 발행됨)" : " (미발행 — 테마 목록에서 확인)"}
        </div>
      )}

      <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
        <label style={{ cursor: "pointer" }}>
          <input
            type="checkbox"
            checked={publish}
            onChange={(e) => setPublish(e.target.checked)}
            style={{ marginRight: 6 }}
          />
          설치 후 바로 발행 (라이브 적용)
        </label>
        <button onClick={() => void install()} disabled={busy || scopeMissing || !store.connected}>
          {busy ? "설치 중… (zip 처리 대기)" : "테마 설치"}
        </button>
      </div>
    </div>
  );
}
