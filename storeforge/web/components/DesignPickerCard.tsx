"use client";

import { CSSProperties, useEffect, useState } from "react";
import { api, ApiError, type DesignPreset, type Store } from "@/lib/api";

/**
 * 헤더/푸터 디자인 프리셋 선택 — 참조 UI 킷 기반.
 *
 * 서버(engine/design_presets.py)의 프리셋 id 와 여기 와이어프레임이 1:1 이다.
 * 미리보기는 실제 렌더가 아니라 구조 와이어프레임 — "어떤 배치인지"를 고르는 용도이고,
 * 실제 색·폰트는 스토어에 주입된 팔레트를 따른다. 적용하면 라이브 테마가 즉시 바뀐다.
 */

type Tone = "light" | "dark" | "accent";

const TONE_KO: Record<Tone, string> = { light: "라이트", dark: "다크", accent: "액센트" };

const PALETTE: Record<Tone, { bg: string; fg: string; dim: string; line: string }> = {
  light: { bg: "#ffffff", fg: "#1a1a1a", dim: "#9a9a9a", line: "#e3e3e3" },
  dark: { bg: "#181818", fg: "#f2f2f2", dim: "#8a8a8a", line: "#333333" },
  accent: { bg: "#8a6d2f", fg: "#ffffff", dim: "#e8dcc0", line: "#a58a4d" },
};

/* ---------- 와이어프레임 프리미티브 ---------- */

const bar = (w: number | string, h: number, color: string, r = 2): CSSProperties => ({
  width: w,
  height: h,
  background: color,
  borderRadius: r,
  flex: "0 0 auto",
});

function Row({ style, children }: { style?: CSSProperties; children: React.ReactNode }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 5, width: "100%", ...style }}>
      {children}
    </div>
  );
}

function Dots({ n, color }: { n: number; color: string }) {
  return (
    <div style={{ display: "flex", gap: 4 }}>
      {Array.from({ length: n }).map((_, i) => (
        <span key={i} style={{ ...bar(6, 6, color, 3) }} />
      ))}
    </div>
  );
}

function Logo({ color }: { color: string }) {
  return <span style={{ ...bar(34, 8, color, 1) }} />;
}

function MenuBars({ n, color }: { n: number; color: string }) {
  return (
    <div style={{ display: "flex", gap: 6 }}>
      {Array.from({ length: n }).map((_, i) => (
        <span key={i} style={{ ...bar(16, 4, color) }} />
      ))}
    </div>
  );
}

function SearchPill({ color, grow }: { color: string; grow?: boolean }) {
  return (
    <span
      style={{
        flex: grow ? 1 : "0 0 auto",
        height: 12,
        border: `1px solid ${color}`,
        borderRadius: 7,
        minWidth: 40,
      }}
    />
  );
}

function PayChips({ color }: { color: string }) {
  return (
    <div style={{ display: "flex", gap: 4 }}>
      {Array.from({ length: 4 }).map((_, i) => (
        <span key={i} style={{ ...bar(18, 11, "transparent", 2), border: `1px solid ${color}` }} />
      ))}
    </div>
  );
}

function Col({ lines, color, head }: { lines: number; color: string; head: string }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      <span style={{ ...bar(24, 5, head) }} />
      {Array.from({ length: lines }).map((_, i) => (
        <span key={i} style={{ ...bar(30, 3, color) }} />
      ))}
    </div>
  );
}

/* ---------- 프리셋별 와이어프레임 ---------- */

function HeaderWire({ id, tone }: { id: string; tone: Tone }) {
  const p = PALETTE[tone];
  const frame: CSSProperties = {
    background: p.bg,
    border: `1px solid ${p.line}`,
    borderRadius: 4,
    padding: "8px 10px",
    display: "flex",
    flexDirection: "column",
    gap: 6,
    minHeight: 44,
    justifyContent: "center",
  };
  const spread: CSSProperties = { justifyContent: "space-between" };
  switch (id) {
    case "classic-inline":
      return (
        <div style={frame}>
          <Row style={spread}>
            <Logo color={p.fg} />
            <MenuBars n={5} color={p.dim} />
            <Dots n={3} color={p.fg} />
          </Row>
        </div>
      );
    case "center-logo":
      return (
        <div style={frame}>
          <Row style={spread}>
            <MenuBars n={2} color={p.dim} />
            <Logo color={p.fg} />
            <Dots n={1} color={p.fg} />
          </Row>
        </div>
      );
    case "search-bar":
      return (
        <div style={frame}>
          <Row style={spread}>
            <Logo color={p.fg} />
            <SearchPill color={p.dim} grow />
            <Dots n={2} color={p.fg} />
          </Row>
          <Row style={{ justifyContent: "center" }}>
            <MenuBars n={6} color={p.dim} />
          </Row>
        </div>
      );
    case "menu-right":
      return (
        <div style={frame}>
          <Row style={spread}>
            <Logo color={p.fg} />
            <Row style={{ width: "auto", gap: 8 }}>
              <MenuBars n={5} color={p.dim} />
              <Dots n={1} color={p.fg} />
            </Row>
          </Row>
        </div>
      );
    case "compact":
      return (
        <div style={{ ...frame, minHeight: 30, padding: "5px 10px" }}>
          <Row style={spread}>
            <Logo color={p.fg} />
            <MenuBars n={4} color={p.dim} />
          </Row>
        </div>
      );
    case "double-row":
      return (
        <div style={frame}>
          <Row style={spread}>
            <MenuBars n={2} color={p.dim} />
            <Dots n={2} color={p.dim} />
          </Row>
          <Row style={{ justifyContent: "center" }}>
            <Logo color={p.fg} />
          </Row>
          <Row style={{ justifyContent: "center" }}>
            <MenuBars n={7} color={p.dim} />
          </Row>
        </div>
      );
    default:
      return <div style={frame} />;
  }
}

function FooterWire({ id, tone }: { id: string; tone: Tone }) {
  const p = PALETTE[tone];
  const frame: CSSProperties = {
    background: p.bg,
    border: `1px solid ${p.line}`,
    borderRadius: 4,
    padding: "10px 12px",
    display: "flex",
    flexDirection: "column",
    gap: 8,
    minHeight: 96,
    justifyContent: "center",
  };
  const hr = <span style={{ ...bar("100%", 1, p.line, 0) }} />;
  const center: CSSProperties = { justifyContent: "center" };
  const spread: CSSProperties = { justifyContent: "space-between" };
  const copyright = <span style={{ ...bar(56, 3, p.dim) }} />;
  switch (id) {
    case "trust-payments":
      return (
        <div style={frame}>
          <Row style={center}><span style={{ ...bar(70, 6, p.fg) }} /></Row>
          <Row style={center}><PayChips color={p.dim} /></Row>
          {hr}
          <Row style={spread}>
            <Logo color={p.fg} />
            <MenuBars n={4} color={p.dim} />
          </Row>
          <Row style={center}>{copyright}</Row>
        </div>
      );
    case "newsletter":
      return (
        <div style={frame}>
          <Row style={spread}>
            <Logo color={p.fg} />
            <MenuBars n={4} color={p.dim} />
            <Dots n={3} color={p.fg} />
          </Row>
          {hr}
          <Row style={center}>
            <span style={{ ...bar(60, 5, p.fg) }} />
          </Row>
          <Row style={center}>
            <SearchPill color={p.dim} />
            <span style={{ ...bar(14, 12, p.fg, 2) }} />
          </Row>
        </div>
      );
    case "contact-columns":
      return (
        <div style={frame}>
          <Row style={{ ...spread, alignItems: "flex-start" }}>
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              <Logo color={p.fg} />
              <span style={{ ...bar(40, 3, p.dim) }} />
              <span style={{ ...bar(34, 3, p.dim) }} />
            </div>
            <Col lines={3} color={p.dim} head={p.fg} />
            <Col lines={2} color={p.dim} head={p.fg} />
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              <span style={{ ...bar(24, 5, p.fg) }} />
              <Dots n={3} color={p.fg} />
            </div>
          </Row>
          <Row style={center}>{copyright}</Row>
        </div>
      );
    case "centered-social":
      return (
        <div style={frame}>
          <Row style={center}><Logo color={p.fg} /></Row>
          <Row style={center}><Dots n={4} color={p.fg} /></Row>
          <Row style={center}><MenuBars n={4} color={p.dim} /></Row>
          <Row style={center}>{copyright}</Row>
        </div>
      );
    case "mega-dark":
      return (
        <div style={frame}>
          <Row style={{ ...spread, alignItems: "flex-start" }}>
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              <Logo color={p.fg} />
              <span style={{ ...bar(42, 3, p.dim) }} />
              <span style={{ ...bar(36, 3, p.dim) }} />
              <Dots n={3} color={p.fg} />
            </div>
            <Col lines={4} color={p.dim} head={p.fg} />
            <Col lines={4} color={p.dim} head={p.fg} />
            <Col lines={2} color={p.dim} head={p.fg} />
          </Row>
          {hr}
          <Row style={spread}>{copyright}<span style={{ ...bar(40, 3, p.dim) }} /></Row>
        </div>
      );
    case "slim-bar":
      return (
        <div style={{ ...frame, minHeight: 52 }}>
          <Row style={spread}>
            <MenuBars n={3} color={p.dim} />
            <Logo color={p.fg} />
            <Dots n={3} color={p.fg} />
          </Row>
          <Row style={center}>{copyright}</Row>
        </div>
      );
    case "info-payments-dark":
      return (
        <div style={frame}>
          <Row style={{ ...spread, alignItems: "flex-start" }}>
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              <Logo color={p.fg} />
              <span style={{ ...bar(42, 3, p.dim) }} />
            </div>
            <Col lines={3} color={p.dim} head={p.fg} />
            <Col lines={3} color={p.dim} head={p.fg} />
          </Row>
          {hr}
          <Row style={spread}>
            <PayChips color={p.dim} />
            <Dots n={3} color={p.fg} />
          </Row>
        </div>
      );
    case "minimal-centered":
      return (
        <div style={frame}>
          <Row style={center}><MenuBars n={5} color={p.fg} /></Row>
          <Row style={center}><Dots n={3} color={p.fg} /></Row>
          <Row style={center}><PayChips color={p.dim} /></Row>
          <Row style={center}>{copyright}</Row>
        </div>
      );
    default:
      return <div style={frame} />;
  }
}

/* ---------- 선택 그리드 ---------- */

function PresetGrid({
  kind,
  presets,
  store,
  scopeMissing,
}: {
  kind: "header" | "footer";
  presets: DesignPreset[];
  store: Store;
  scopeMissing: boolean;
}) {
  const [selected, setSelected] = useState<string>("");
  const [tone, setTone] = useState<Tone | "">("");
  const [applying, setApplying] = useState(false);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");

  const sel = presets.find((x) => x.id === selected);
  // 미리보기 톤: 사용자가 고른 톤 > 프리셋 기본 톤(푸터) > 라이트(헤더)
  const previewTone = (t?: string): Tone =>
    (tone || (t as Tone) || "light") as Tone;

  async function apply() {
    if (!sel) return;
    setApplying(true);
    setError("");
    setOk("");
    try {
      const body = { preset_id: sel.id, ...(tone ? { tone } : {}) };
      const r =
        kind === "header"
          ? await api.applyHeaderDesign(store.id, body)
          : await api.applyFooterDesign(store.id, body);
      setOk(
        `'${sel.name}' 적용 완료 (${TONE_KO[r.tone as Tone] ?? r.tone} · ${r.scheme_id}) — ` +
          `스토어프론트를 새로고침해 확인하세요.`
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setApplying(false);
    }
  }

  return (
    <div>
      {error && <div className="err">{error}</div>}
      {ok && <div className="ok">{ok}</div>}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(230px, 1fr))",
          gap: 10,
          marginBottom: 10,
        }}
      >
        {presets.map((p) => (
          <div
            key={p.id}
            onClick={() => setSelected(p.id === selected ? "" : p.id)}
            style={{
              cursor: "pointer",
              border:
                p.id === selected
                  ? "2px solid var(--accent, #82a31a)"
                  : "1px solid var(--border, #ddd)",
              borderRadius: 8,
              padding: 8,
              background: p.id === selected ? "rgba(130,163,26,.06)" : "transparent",
            }}
          >
            {kind === "header" ? (
              <HeaderWire id={p.id} tone={previewTone(p.tone)} />
            ) : (
              <FooterWire id={p.id} tone={previewTone(p.tone)} />
            )}
            <div style={{ marginTop: 6, fontWeight: 600, fontSize: 13 }}>{p.name}</div>
            <div style={{ fontSize: 11, color: "var(--muted)", lineHeight: 1.4 }}>
              {p.description}
            </div>
          </div>
        ))}
      </div>
      <div className="row" style={{ gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <span style={{ fontSize: 12, color: "var(--muted)" }}>톤:</span>
        {(["", "light", "dark", "accent"] as const).map((t) => (
          <button
            key={t || "auto"}
            className={tone === t ? undefined : "ghost"}
            style={{ fontSize: 12 }}
            onClick={() => setTone(t)}
          >
            {t === "" ? "자동(프리셋 기본)" : TONE_KO[t]}
          </button>
        ))}
        <button
          onClick={() => void apply()}
          disabled={!sel || applying || scopeMissing || !store.connected}
          style={{ marginLeft: "auto" }}
        >
          {applying
            ? "적용 중…"
            : sel
              ? `'${sel.name}' 라이브에 적용`
              : "프리셋을 선택하세요"}
        </button>
      </div>
    </div>
  );
}

/* ---------- 카드 본체 ---------- */

export default function DesignPickerCard({ store }: { store: Store }) {
  const [tab, setTab] = useState<"header" | "footer">("footer");
  const [headers, setHeaders] = useState<DesignPreset[]>([]);
  const [footers, setFooters] = useState<DesignPreset[]>([]);
  const [loadError, setLoadError] = useState("");

  const scopeMissing =
    store.granted_scopes.length > 0 && !store.granted_scopes.includes("write_themes");

  useEffect(() => {
    let alive = true;
    Promise.all([api.designHeaders(), api.designFooters()])
      .then(([h, f]) => {
        if (!alive) return;
        setHeaders(h.presets);
        setFooters(f.presets);
      })
      .catch((err) => alive && setLoadError(err instanceof ApiError ? err.message : String(err)));
    return () => {
      alive = false;
    };
  }, []);

  return (
    <div className="card">
      <h2>헤더·푸터 디자인</h2>
      <p className="sub" style={{ fontSize: 12, marginBottom: 12 }}>
        참조 UI 킷 기반 프리셋입니다. 미리보기는 배치 와이어프레임 — 실제 색·폰트는 이
        스토어에 주입된 팔레트를 따릅니다. 적용하면 <b>라이브 테마가 즉시</b> 바뀝니다
        (로고·메뉴·소셜 링크 등 스토어 데이터는 유지).
      </p>
      {scopeMissing && (
        <div className="err">
          <span className="mono">write_themes</span> 스코프가 없어 적용이 잠깁니다.
        </div>
      )}
      {loadError && <div className="err">{loadError}</div>}
      <div className="row" style={{ gap: 6, marginBottom: 12 }}>
        <button className={tab === "footer" ? undefined : "ghost"} onClick={() => setTab("footer")}>
          푸터 8종
        </button>
        <button className={tab === "header" ? undefined : "ghost"} onClick={() => setTab("header")}>
          헤더 6종
        </button>
      </div>
      {tab === "header" ? (
        <PresetGrid kind="header" presets={headers} store={store} scopeMissing={scopeMissing} />
      ) : (
        <PresetGrid kind="footer" presets={footers} store={store} scopeMissing={scopeMissing} />
      )}
    </div>
  );
}
