"use client";

import { useState } from "react";
import { api, ApiError, type NavItem, type Store } from "@/lib/api";

const TYPE_KO: Record<string, string> = {
  FRONTPAGE: "홈",
  COLLECTION: "컬렉션",
  PAGE: "페이지",
  HTTP: "링크",
};

/**
 * 6단계 — 메뉴 구성.
 *
 * 페이지·컬렉션을 만들어도 메뉴에 안 걸려 있으면 손님이 못 찾아간다.
 * 스토어에 실제로 있는 것들로 헤더/푸터 구조를 제안받고, 확인 후 반영한다.
 * 기존 main-menu / footer 메뉴를 갱신하므로 테마 설정은 건드리지 않는다.
 */
export default function NavigationCard({ store }: { store: Store }) {
  const [headerItems, setHeaderItems] = useState<NavItem[] | null>(null);
  const [footerItems, setFooterItems] = useState<NavItem[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [applying, setApplying] = useState(false);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");

  const scopeMissing =
    store.granted_scopes.length > 0 &&
    !store.granted_scopes.includes("write_online_store_navigation");

  async function runPreview() {
    setLoading(true);
    setError("");
    setOk("");
    try {
      const p = await api.navPreview(store.id);
      setHeaderItems(p.header);
      setFooterItems(p.footer);
      if (!p.header_menu_found) {
        setError("이 스토어에 main-menu 핸들의 메뉴가 없습니다 — 반영 시 헤더는 건너뜁니다.");
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  async function runApply() {
    setApplying(true);
    setError("");
    setOk("");
    try {
      const r = await api.navApply(store.id, {
        header: headerItems ?? [],
        footer: footerItems ?? [],
      });
      setOk(`메뉴 반영 완료 — ${r.applied.join(", ")}. 스토어프론트를 새로고침하세요.`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setApplying(false);
    }
  }

  const list = (
    label: string,
    items: NavItem[] | null,
    setItems: (v: NavItem[]) => void
  ) =>
    items && (
      <div style={{ flex: 1, minWidth: 260 }}>
        <h3 style={{ margin: "0 0 6px" }}>{label}</h3>
        {items.length === 0 && (
          <p style={{ fontSize: 12, color: "var(--muted)" }}>항목 없음 — 반영 시 건너뜁니다.</p>
        )}
        {items.map((it, i) => (
          <div key={i} className="row" style={{ gap: 6, marginBottom: 4, alignItems: "center" }}>
            <span className="pill" style={{ flex: "0 0 auto" }}>
              {TYPE_KO[it.type] ?? it.type}
            </span>
            <input
              value={it.title}
              onChange={(e) =>
                setItems(items.map((x, j) => (i === j ? { ...x, title: e.target.value } : x)))
              }
              style={{ flex: 1 }}
            />
            <button
              className="ghost"
              title="이 항목 빼기"
              onClick={() => setItems(items.filter((_, j) => j !== i))}
            >
              ✕
            </button>
          </div>
        ))}
      </div>
    );

  return (
    <div className="card">
      <h2>6단계 — 메뉴 구성</h2>
      <p className="sub" style={{ fontSize: 12, marginBottom: 12 }}>
        만든 컬렉션·페이지를 헤더(main-menu)와 푸터(footer)에 겁니다. 먼저 제안을 받아
        항목을 다듬은 뒤 반영하세요 — 기존 메뉴를 통째로 교체합니다.
      </p>

      {scopeMissing && (
        <div className="err">
          <span className="mono">write_online_store_navigation</span> 스코프가 없어 반영은
          잠깁니다 — 앱 버전에 추가 후 재설치하세요. (제안 미리보기는 됩니다)
        </div>
      )}
      {error && <div className="err">{error}</div>}
      {ok && <div className="ok">{ok}</div>}

      <div className="row" style={{ marginBottom: 12 }}>
        <button onClick={() => void runPreview()} disabled={loading || !store.connected}>
          {loading ? "구성 중…" : "메뉴 구성 제안 받기"}
        </button>
        {headerItems && (
          <button
            onClick={() => void runApply()}
            disabled={applying || scopeMissing || !store.connected}
          >
            {applying ? "반영 중…" : "메뉴 반영"}
          </button>
        )}
      </div>

      <div className="row" style={{ gap: 20, alignItems: "flex-start", flexWrap: "wrap" }}>
        {list("헤더 (main-menu)", headerItems, (v) => setHeaderItems(v))}
        {list("푸터 (footer)", footerItems, (v) => setFooterItems(v))}
      </div>
    </div>
  );
}
