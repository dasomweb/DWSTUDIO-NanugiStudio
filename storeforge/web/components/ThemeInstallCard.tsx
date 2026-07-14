"use client";

import { useEffect, useState } from "react";
import { api, ApiError, type Store, type ThemeInstall, type ThemeSource } from "@/lib/api";

/**
 * 소스 테마 설치 카드 (기획안 §6.3).
 *
 * 릴리즈(v* 태그)의 theme.zip 을 themeCreate 로 넣어 이 스토어에 **GitHub 미연동 테마**를
 * 만든다. 버전은 프로젝트별로 격리된다 — 이 스토어에 설치된 버전이 기록되고, 새 릴리즈가
 * 나와도 저절로 바뀌지 않는다. 색상은 여기서 정하지 않는다: 설치 후 브랜드 주입(축①)이
 * metafield 로 입히므로, 같은 버전의 zip 은 모든 스토어에 동일하다.
 */
export default function ThemeInstallCard({
  store,
  onInstalled,
}: {
  store: Store;
  onInstalled?: () => void;
}) {
  const [source, setSource] = useState<ThemeSource | null>(null);
  const [version, setVersion] = useState(""); // 비우면 latest
  const [publish, setPublish] = useState(true);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<ThemeInstall | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.themeSource().then(setSource).catch(() => {});
  }, []);

  const scopeMissing =
    store.granted_scopes.length > 0 && !store.granted_scopes.includes("write_themes");

  async function install() {
    setBusy(true);
    setError("");
    setResult(null);
    try {
      const r = await api.installTheme(store.id, publish, version.trim() || undefined);
      setResult(r);
      onInstalled?.();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card" style={{ marginBottom: 20 }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}>
        <h2 style={{ margin: 0, flex: 1 }}>테마</h2>
        <span style={{ fontSize: 13, color: "var(--muted)" }}>
          이 스토어:{" "}
          {store.installed_theme_version ? (
            <strong className="mono">{store.installed_theme_version}</strong>
          ) : (
            "미설치"
          )}
          {source?.latest_version && (
            <>
              {" · "}최신 릴리즈: <span className="mono">{source.latest_version}</span>
            </>
          )}
        </span>
      </div>

      <p style={{ color: "var(--muted)", fontSize: 13 }}>
        소스 테마 릴리즈를 이 스토어에 <strong>GitHub 미연동 테마</strong>로 설치합니다.
        기존 테마는 삭제되지 않으므로 잘못돼도 되돌릴 수 있습니다. 색상·폰트는 설치 후 아래
        브랜드 주입이 입힙니다.
      </p>

      {scopeMissing && (
        <div className="err">
          <span className="mono">write_themes</span> 스코프가 없어 설치할 수 없습니다.
        </div>
      )}
      {error && <div className="err">{error}</div>}
      {result && (
        <div className="ok">
          설치 완료 — <strong>{result.theme_name}</strong>{" "}
          (<span className="mono">{result.version}</span>
          {result.published ? " · 라이브로 발행됨" : " · 미발행"})
        </div>
      )}

      <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
        <input
          value={version}
          onChange={(e) => setVersion(e.target.value)}
          placeholder={source?.latest_version ? `비우면 최신 (${source.latest_version})` : "비우면 최신"}
          className="mono"
          style={{ width: 220 }}
        />
        <label style={{ cursor: "pointer" }}>
          <input
            type="checkbox"
            checked={publish}
            onChange={(e) => setPublish(e.target.checked)}
            style={{ marginRight: 6 }}
          />
          설치 후 바로 발행
        </label>
        <button onClick={() => void install()} disabled={busy || scopeMissing || !store.connected}>
          {busy ? "설치 중… (zip 처리 대기)" : "테마 설치"}
        </button>
      </div>
    </div>
  );
}
