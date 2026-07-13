"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import Shell from "@/components/Shell";
import CredentialsFields from "@/components/CredentialsFields";
import {
  api,
  ApiError,
  type BrandInput,
  type Credentials,
  type Font,
  type Preview,
  type Run,
  type Store,
} from "@/lib/api";

const DEFAULT_BRAND: BrandInput = {
  primary: "#000000",
  background: "#ffffff",
  foreground: "#000000",
  accent: "#82a31a",
  body_font: "pretendard",
  heading_font: "bebas-neue",
  subheading_font: "oswald",
  accent_font: "bebas-neue",
  page_width: "narrow",
};

const ROLE_KO: Record<string, string> = {
  light: "기본",
  light_alt: "기본 변주",
  dark: "반전",
  dark_alt: "반전 변주",
  primary: "주색 채움",
  primary_deep: "주색 딥",
  accent: "액센트",
  neutral: "뉴트럴",
};

/** 스킴 하나를 실제 CSS 변수로 렌더한 카드. 테마에서 보이는 것과 같은 색 조합이다. */
function SchemeCard({
  css,
  role,
  minRatio,
  pass,
}: {
  css: Record<string, string>;
  role: string;
  minRatio: number;
  pass: boolean;
}) {
  const v = (k: string) => css[k] ?? "";
  return (
    <div className="scheme">
      <div className="body" style={{ background: v("--color-background") }}>
        <div className="name" style={{ color: v("--color-foreground") }}>
          {ROLE_KO[role] ?? role}
        </div>
        <div className="title" style={{ color: v("--color-foreground-heading") }}>
          브랜드 헤드라인
        </div>
        <div className="text" style={{ color: v("--color-foreground") }}>
          본문 텍스트가 이렇게 보입니다.
        </div>
        <div className="btns">
          <span
            className="btn"
            style={{
              background: v("--color-primary-button-background"),
              color: v("--color-primary-button-text"),
              borderColor: v("--color-primary-button-border"),
            }}
          >
            장바구니 담기
          </span>
          <span
            className="btn"
            style={{
              background: v("--color-secondary-button-background"),
              color: v("--color-secondary-button-text"),
              borderColor: v("--color-secondary-button-border"),
            }}
          >
            더 보기
          </span>
        </div>
      </div>
      <div className="meta">
        <span className="mono">최저 대비 {minRatio}</span>
        <span className={pass ? "pill ok" : "pill bad"}>{pass ? "AA" : "미달"}</span>
      </div>
    </div>
  );
}

export default function StoreDetailPage() {
  const params = useParams<{ id: string }>();
  const storeId = Number(params.id);

  const [store, setStore] = useState<Store | null>(null);
  const [fonts, setFonts] = useState<Font[]>([]);
  const [runs, setRuns] = useState<Run[]>([]);
  const [applied, setApplied] = useState<boolean | null>(null);

  const [brand, setBrand] = useState<BrandInput>(DEFAULT_BRAND);
  const [preview, setPreview] = useState<Preview | null>(null);

  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // 축① LLM 단계 — 자연어 → 색 4개 + 폰트 4개
  const [description, setDescription] = useState("");
  const [rationale, setRationale] = useState<string | null>(null);
  const [thinking, setThinking] = useState(false);

  // 자격증명 교체
  const [editingCreds, setEditingCreds] = useState(false);
  const [creds, setCreds] = useState<Credentials>({ auth_type: "client_credentials" });

  const load = useCallback(async () => {
    try {
      const [stores, f, r] = await Promise.all([
        api.listStores(),
        api.listFonts(),
        api.listRuns(storeId),
      ]);
      setStore(stores.find((s) => s.id === storeId) ?? null);
      setFonts(f);
      setRuns(r);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    }
  }, [storeId]);

  useEffect(() => {
    void load();
  }, [load]);

  // 연결된 스토어에 한해 현재 주입 상태를 읽는다 (Shopify 왕복이므로 실패해도 치명적이지 않다).
  useEffect(() => {
    if (!store?.connected) return;
    api
      .currentBrand(storeId)
      .then((r) => setApplied(r.applied))
      .catch(() => setApplied(null));
  }, [store?.connected, storeId]);

  // 입력이 바뀔 때마다 서버에서 파생 결과를 다시 받는다 (색 계산은 전부 서버가 한다).
  useEffect(() => {
    let cancelled = false;
    const t = setTimeout(() => {
      api
        .preview(brand)
        .then((p) => !cancelled && setPreview(p))
        .catch((err) => !cancelled && setError(err.message));
    }, 200);
    return () => {
      cancelled = true;
      clearTimeout(t);
    };
  }, [brand]);

  const set = <K extends keyof BrandInput>(k: K, v: BrandInput[K]) =>
    setBrand((b) => ({ ...b, [k]: v }));

  const auditByScheme = useMemo(() => {
    const m = new Map<string, { min: number; pass: boolean; role: string }>();
    preview?.report.schemes.forEach((s) => {
      const min = Math.min(...Object.values(s.checks).map((c) => c.ratio));
      m.set(s.id, { min, pass: s.pass, role: s.role });
    });
    return m;
  }, [preview]);

  async function testConnection() {
    setError(null);
    setOk(null);
    try {
      setStore(await api.testStore(storeId));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    }
  }

  async function saveCredentials(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const updated = await api.updateCredentials(storeId, creds);
      setStore(updated);
      setEditingCreds(false);
      setCreds({ auth_type: "client_credentials" });
      setOk("자격증명을 교체하고 연결 테스트를 실행했습니다.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function runInterpret() {
    setThinking(true);
    setError(null);
    setRationale(null);
    try {
      const res = await api.interpret(description);
      // LLM 은 색/폰트만 정한다. 나머지 441개 값은 파생 엔진이 만든다.
      setBrand(res.brand);
      setRationale(res.rationale);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setThinking(false);
    }
  }

  async function apply(force: boolean) {
    setBusy(true);
    setError(null);
    setOk(null);
    try {
      await api.apply(storeId, brand, force);
      setOk("브랜드 설정을 스토어에 주입했습니다. 테마를 새로고침하면 반영됩니다.");
      setApplied(true);
      setRuns(await api.listRuns(storeId));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  if (!store) {
    return (
      <Shell>
        {error ? <div className="err">{error}</div> : <p className="sub">불러오는 중…</p>}
      </Shell>
    );
  }

  const fontSelect = (key: keyof BrandInput, label: string) => (
    <div>
      <label htmlFor={key}>{label}</label>
      <select
        id={key}
        value={brand[key] as string}
        onChange={(e) => set(key, e.target.value as never)}
      >
        {fonts.map((f) => (
          <option key={f.handle} value={f.handle}>
            {f.family}
            {f.korean ? " (한글)" : ""}
          </option>
        ))}
      </select>
    </div>
  );

  const colorInput = (key: "primary" | "background" | "foreground" | "accent", label: string) => (
    <div>
      <label htmlFor={key}>{label}</label>
      <div className="row" style={{ gap: 6, flexWrap: "nowrap" }}>
        <input
          id={key}
          type="color"
          style={{ width: 46, flex: "0 0 46px" }}
          value={(brand[key] as string) ?? "#000000"}
          onChange={(e) => set(key, e.target.value)}
        />
        <input
          className="mono"
          value={(brand[key] as string) ?? ""}
          onChange={(e) => set(key, e.target.value)}
        />
      </div>
    </div>
  );

  return (
    <Shell>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div>
          <h1>{store.name}</h1>
          <p className="sub mono">{store.shop_domain}</p>
        </div>
        <div className="row">
          {store.connected ? (
            <span className="pill ok">연결됨</span>
          ) : (
            <span className="pill bad">연결 안 됨</span>
          )}
          {applied === true && <span className="pill">온보딩 적용됨</span>}
        </div>
      </div>

      {error && <div className="err">{error}</div>}
      {ok && (
        <div className="note" style={{ marginBottom: 16, color: "var(--ok)" }}>
          {ok}
        </div>
      )}
      {!store.connected && (
        <div className="err">
          연결이 확인되지 않았습니다. 자격증명을 확인하고 연결 테스트를 통과시켜야 주입할 수
          있습니다.
          {store.last_error ? ` — ${store.last_error}` : ""}
        </div>
      )}

      <div className="card">
        <div className="row" style={{ justifyContent: "space-between", marginBottom: 12 }}>
          <h2 style={{ margin: 0 }}>연동 · 스코프</h2>
          <div className="row">
            <button className="ghost" onClick={testConnection}>
              연결 테스트
            </button>
            {!editingCreds && (
              <button className="ghost" onClick={() => setEditingCreds(true)}>
                자격증명 교체
              </button>
            )}
          </div>
        </div>

        <table style={{ marginBottom: editingCreds ? 16 : 0 }}>
          <tbody>
            <tr>
              <th style={{ width: 160 }}>인증 방식</th>
              <td>
                {store.auth_type === "client_credentials"
                  ? "Client ID / Secret (토큰 자동 발급)"
                  : "영구 액세스 토큰"}
              </td>
            </tr>
            <tr>
              <th>스토어</th>
              <td>
                {store.shop_name ?? "—"}{" "}
                {store.shop_plan && (
                  <span style={{ color: "var(--muted)" }}>· {store.shop_plan}</span>
                )}
              </td>
            </tr>
            <tr>
              <th>필수 스코프</th>
              <td>
                {store.required_scopes.map((s) => {
                  const has = store.granted_scopes.includes(s);
                  return (
                    <span
                      key={s}
                      className={`pill ${store.granted_scopes.length === 0 ? "" : has ? "ok" : "bad"}`}
                      style={{ marginRight: 6 }}
                    >
                      {store.granted_scopes.length === 0 ? "?" : has ? "✓" : "✗"}{" "}
                      <span className="mono">{s}</span>
                    </span>
                  );
                })}
                {store.recommended_scopes.map((s) => {
                  const has = store.granted_scopes.includes(s);
                  return (
                    <span key={s} className="pill" style={{ marginRight: 6, opacity: 0.75 }}>
                      {store.granted_scopes.length === 0 ? "?" : has ? "✓" : "—"}{" "}
                      <span className="mono">{s}</span> (권장)
                    </span>
                  );
                })}
              </td>
            </tr>
            <tr>
              <th>부여된 스코프</th>
              <td className="mono" style={{ color: "var(--muted)", fontSize: 12 }}>
                {store.granted_scopes.length > 0
                  ? store.granted_scopes.join(", ")
                  : "아직 확인되지 않았습니다 (연결 테스트를 실행하세요)"}
              </td>
            </tr>
          </tbody>
        </table>

        {store.missing_scopes.length > 0 && (
          <div className="err" style={{ marginTop: 12, marginBottom: 0 }}>
            <strong>{store.missing_scopes.join(", ")}</strong> 스코프가 없습니다. Dev Dashboard 에서
            해당 앱의 Admin API 스코프에 추가해 <strong>새 버전을 Release</strong> 하고,{" "}
            <strong>앱을 재설치</strong>한 뒤 연결 테스트를 다시 하세요.
          </div>
        )}

        {editingCreds && (
          <form onSubmit={saveCredentials} style={{ borderTop: "1px solid var(--line)", paddingTop: 16 }}>
            <CredentialsFields value={creds} onChange={setCreds} idPrefix="edit" />
            <div className="row">
              <button type="submit" disabled={busy}>
                {busy ? "확인 중…" : "저장하고 연결 테스트"}
              </button>
              <button type="button" className="ghost" onClick={() => setEditingCreds(false)}>
                취소
              </button>
            </div>
          </form>
        )}
      </div>

      <div className="card">
        <h2>브랜드 설명 → AI 해석</h2>
        <p className="sub" style={{ fontSize: 12, marginBottom: 12 }}>
          브랜드를 한국어로 설명하면 AI가 색 4개와 폰트 4개를 고릅니다. 고른 값은 아래에서
          그대로 수정할 수 있습니다.
        </p>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="예) 20대 여성 타겟 미니멀 패션 브랜드. 크림톤 배경에 절제된 느낌. 한국어 상세페이지 위주."
          rows={3}
          style={{
            width: "100%",
            background: "var(--bg)",
            border: "1px solid var(--line)",
            color: "var(--text)",
            borderRadius: 8,
            padding: "9px 10px",
            font: "inherit",
            resize: "vertical",
            marginBottom: 12,
          }}
        />
        <div className="row">
          <button onClick={runInterpret} disabled={thinking || !description.trim()}>
            {thinking ? "AI가 브랜드를 해석하는 중…" : "AI로 브랜드 생성"}
          </button>
        </div>
        {rationale && (
          <div className="note" style={{ marginTop: 12 }}>
            <strong style={{ color: "var(--text)" }}>AI 근거</strong>
            <div style={{ marginTop: 4 }}>{rationale}</div>
          </div>
        )}
      </div>

      <div className="card">
        <h2>브랜드</h2>
        <p className="sub" style={{ fontSize: 12, marginBottom: 16 }}>
          여기 입력하는 <strong>색 3~4개</strong>가 전부입니다. 나머지{" "}
          <strong>{preview?.report.value_count ?? "—"}개</strong> CSS 값은 파생 엔진이
          결정론적으로 만들고 WCAG 대비까지 자동 보정합니다.
        </p>

        <div className="grid four" style={{ marginBottom: 16 }}>
          {colorInput("primary", "주색 (Primary)")}
          {colorInput("background", "배경")}
          {colorInput("foreground", "본문 텍스트")}
          {colorInput("accent", "액센트")}
        </div>

        <div className="grid four" style={{ marginBottom: 16 }}>
          {fontSelect("body_font", "본문 폰트")}
          {fontSelect("heading_font", "헤딩 폰트")}
          {fontSelect("subheading_font", "서브헤딩 폰트")}
          {fontSelect("accent_font", "액센트 폰트")}
        </div>

        <div style={{ maxWidth: 200 }}>
          <label htmlFor="page_width">페이지 폭</label>
          <select
            id="page_width"
            value={brand.page_width}
            onChange={(e) => set("page_width", e.target.value as BrandInput["page_width"])}
          >
            <option value="narrow">좁게</option>
            <option value="medium">보통</option>
            <option value="wide">넓게</option>
          </select>
        </div>
      </div>

      <div className="card">
        <div className="row" style={{ justifyContent: "space-between", marginBottom: 12 }}>
          <h2 style={{ margin: 0 }}>미리보기 — 9개 컬러 스킴</h2>
          {preview && (
            <span className={preview.report.wcag_pass ? "pill ok" : "pill bad"}>
              WCAG {preview.report.wcag_pass ? "전체 통과" : "미달 있음"}
            </span>
          )}
        </div>

        {preview ? (
          <div className="schemes">
            {preview.payload.schemes.map((s) => {
              const a = auditByScheme.get(s.id);
              return (
                <SchemeCard
                  key={s.id}
                  css={s.css}
                  role={a?.role ?? ""}
                  minRatio={a?.min ?? 0}
                  pass={a?.pass ?? false}
                />
              );
            })}
          </div>
        ) : (
          <p className="sub" style={{ margin: 0 }}>
            계산 중…
          </p>
        )}
      </div>

      <div className="card">
        <h2>주입</h2>
        <div className="note" style={{ marginBottom: 14 }}>
          온보딩은 <strong>1회성</strong>입니다. 이미 적용된 스토어를 다시 덮어쓰면 머천트가 테마
          에디터에서 손댄 값이 사라질 수 있어, 재주입은 명시적으로 선택해야 합니다.
          <span className="mono">
            {" "}
            shop.metafields.storeforge.brand
          </span>{" "}
          에만 씁니다 — 테마 파일은 건드리지 않습니다.
        </div>
        <div className="row">
          <button
            onClick={() => apply(false)}
            disabled={busy || !store.connected || !preview?.report.wcag_pass}
          >
            {busy ? "주입 중…" : "스토어에 적용"}
          </button>
          {applied && (
            <button className="danger" onClick={() => apply(true)} disabled={busy}>
              덮어쓰기 (재주입)
            </button>
          )}
        </div>
      </div>

      <div className="card">
        <h2>실행 이력</h2>
        {runs.length === 0 ? (
          <p className="sub" style={{ margin: 0 }}>
            아직 실행된 온보딩이 없습니다.
          </p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>상태</th>
                <th>시작</th>
                <th>오류</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => (
                <tr key={r.id}>
                  <td className="mono">{r.id}</td>
                  <td>
                    <span className={r.status === "succeeded" ? "pill ok" : "pill bad"}>
                      {r.status === "succeeded" ? "성공" : "실패"}
                    </span>
                  </td>
                  <td className="mono" style={{ color: "var(--muted)" }}>
                    {new Date(r.started_at).toLocaleString("ko-KR")}
                  </td>
                  <td style={{ color: "var(--muted)", fontSize: 12 }}>{r.error ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </Shell>
  );
}
