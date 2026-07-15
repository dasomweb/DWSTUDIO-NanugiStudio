"use client";

import { useEffect, useState } from "react";
import {
  api,
  ApiError,
  type PageDraft,
  type PolicyDraft,
  type Store,
} from "@/lib/api";

/**
 * 5단계 — 페이지 · 정책 · 컬렉션.
 *
 * 페이지/정책은 AI 초안 → **사람 검토·수정** → 반영. 정책은 반영 즉시 라이브라서
 * "검토했습니다" 확인 없이는 버튼이 잠긴다 — AI 초안을 법적 검토 없이 걸면 안 된다.
 * 컬렉션은 스마트 컬렉션(태그 조건)으로 만들어 ListPilot 상품과 자동으로 맞물린다.
 * 컬렉션·상품 페이지 자체는 테마 템플릿이 렌더하므로 여기서 만드는 것은 데이터다.
 */
export default function PagesCard({
  store,
  description,
}: {
  store: Store;
  description: string;
}) {
  const [pageKinds, setPageKinds] = useState<Record<string, string>>({});
  const [policyTypes, setPolicyTypes] = useState<Record<string, string>>({});

  const [drafting, setDrafting] = useState(false);
  const [pages, setPages] = useState<PageDraft[]>([]);
  const [policies, setPolicies] = useState<PolicyDraft[]>([]);

  const [publish, setPublish] = useState(true);
  const [reviewed, setReviewed] = useState(false);
  const [applying, setApplying] = useState(false);

  const [collectionsText, setCollectionsText] = useState("");
  const [collectionsBusy, setCollectionsBusy] = useState(false);

  const [error, setError] = useState("");
  const [ok, setOk] = useState("");

  useEffect(() => {
    api
      .pagesCatalog()
      .then((c) => {
        setPageKinds(c.page_kinds);
        setPolicyTypes(c.policy_types);
      })
      .catch(() => {});
  }, []);

  const scopeMissing = (scope: string) =>
    store.granted_scopes.length > 0 && !store.granted_scopes.includes(scope);

  async function runDraft() {
    setDrafting(true);
    setError("");
    setOk("");
    try {
      const d = await api.draftPages(store.id, {
        description,
        page_kinds: Object.keys(pageKinds),
        policy_types: Object.keys(policyTypes),
      });
      setPages(d.pages);
      setPolicies(d.policies);
      setReviewed(false);
      setOk("초안이 나왔습니다. 아래에서 검토·수정한 뒤 반영하세요 — 특히 [대괄호] 자리는 실제 값으로 채우세요.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setDrafting(false);
    }
  }

  async function runApply() {
    setApplying(true);
    setError("");
    setOk("");
    try {
      const r = await api.applyPages(store.id, {
        pages,
        publish,
        policies,
        policies_reviewed: reviewed,
      });
      setOk(
        `반영 완료 — 페이지 ${r.pages.length}개` +
          (r.pages.length ? ` (${r.pages.map((p) => "/" + "pages/" + p.handle).join(", ")})` : "") +
          (r.policies.length ? `, 정책 ${r.policies.length}건` : "")
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setApplying(false);
    }
  }

  async function runCollections() {
    setCollectionsBusy(true);
    setError("");
    setOk("");
    try {
      const items = collectionsText
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean)
        .map((line) => {
          const [title, tag] = line.split("|").map((s) => s.trim());
          return tag ? { title, tag } : { title };
        });
      const r = await api.createCollections(store.id, items);
      setOk(
        `컬렉션 ${r.created.length}개 생성 — ` +
          r.created.map((c) => `${c.title}${c.smart ? "(스마트)" : ""}`).join(", ")
      );
      setCollectionsText("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setCollectionsBusy(false);
    }
  }

  return (
    <div className="card">
      <h2>5단계 — 페이지 · 정책 · 컬렉션</h2>
      <p className="sub" style={{ fontSize: 12, marginBottom: 12 }}>
        About·Contact·FAQ·배송안내 페이지와 약관·환불·배송·프라이버시 정책을 AI 가 초안으로
        만들고, <strong>검토 후</strong> 반영합니다. 컬렉션(카테고리)·상품 페이지는 데이터만
        만들면 테마가 자동으로 그립니다.
      </p>

      {error && <div className="err">{error}</div>}
      {ok && <div className="ok">{ok}</div>}

      <div className="row">
        <button onClick={() => void runDraft()} disabled={drafting || !description.trim()}>
          {drafting ? "AI가 초안을 쓰는 중… (1분 내외)" : "AI 초안 생성 (페이지 4 + 정책 4)"}
        </button>
        {!description.trim() && (
          <span style={{ fontSize: 12, color: "var(--muted)" }}>
            1단계의 브랜드 설명이 필요합니다
          </span>
        )}
      </div>

      {pages.length > 0 && (
        <div style={{ marginTop: 16 }}>
          <h3 style={{ margin: "0 0 8px" }}>페이지 초안</h3>
          {scopeMissing("write_content") && (
            <div className="err">
              <span className="mono">write_content</span> 스코프가 없어 반영은 잠깁니다 — 앱
              버전에 추가 후 재설치하세요. (초안 검토는 지금 해도 됩니다)
            </div>
          )}
          {pages.map((p, i) => (
            <details key={p.kind} style={{ marginBottom: 10 }} open={i === 0}>
              <summary style={{ cursor: "pointer" }}>
                <strong>{pageKinds[p.kind] ?? p.kind}</strong>{" "}
                <span style={{ color: "var(--muted)", fontSize: 12 }}>— {p.title}</span>
              </summary>
              <input
                value={p.title}
                onChange={(e) =>
                  setPages(pages.map((x, j) => (i === j ? { ...x, title: e.target.value } : x)))
                }
                style={{ width: "100%", margin: "8px 0 6px" }}
              />
              <textarea
                value={p.body_html}
                onChange={(e) =>
                  setPages(pages.map((x, j) => (i === j ? { ...x, body_html: e.target.value } : x)))
                }
                rows={8}
                className="mono"
                style={{ width: "100%", fontSize: 12 }}
              />
            </details>
          ))}

          <h3 style={{ margin: "16px 0 8px" }}>정책 초안</h3>
          <div className="err" style={{ marginBottom: 8 }}>
            ⚠️ 정책은 반영 즉시 <strong>라이브</strong>가 됩니다. AI 초안은 법률 자문을 대체하지
            않습니다 — [대괄호] 자리를 채우고, 가능하면 법적 검토를 거치세요.
          </div>
          {scopeMissing("write_legal_policies") && (
            <div className="err">
              <span className="mono">write_legal_policies</span> 스코프가 없어 정책 반영은 잠깁니다.
            </div>
          )}
          {policies.map((p, i) => (
            <details key={p.type} style={{ marginBottom: 10 }}>
              <summary style={{ cursor: "pointer" }}>
                <strong>{policyTypes[p.type] ?? p.type}</strong>
              </summary>
              <textarea
                value={p.body_html}
                onChange={(e) =>
                  setPolicies(
                    policies.map((x, j) => (i === j ? { ...x, body_html: e.target.value } : x))
                  )
                }
                rows={10}
                className="mono"
                style={{ width: "100%", fontSize: 12, marginTop: 8 }}
              />
            </details>
          ))}

          <div className="row" style={{ marginTop: 12, alignItems: "center", flexWrap: "wrap" }}>
            <label style={{ cursor: "pointer" }}>
              <input
                type="checkbox"
                checked={publish}
                onChange={(e) => setPublish(e.target.checked)}
                style={{ marginRight: 6 }}
              />
              페이지 바로 발행
            </label>
            <label style={{ cursor: "pointer" }}>
              <input
                type="checkbox"
                checked={reviewed}
                onChange={(e) => setReviewed(e.target.checked)}
                style={{ marginRight: 6 }}
              />
              정책 초안을 검토했습니다
            </label>
            <button
              onClick={() => void runApply()}
              disabled={
                applying ||
                !store.connected ||
                (policies.length > 0 && !reviewed) ||
                scopeMissing("write_content")
              }
            >
              {applying ? "반영 중…" : "페이지 · 정책 반영"}
            </button>
          </div>
        </div>
      )}

      <div style={{ borderTop: "1px solid var(--line)", marginTop: 16, paddingTop: 14 }}>
        <strong>컬렉션 (카테고리)</strong>{" "}
        <span style={{ color: "var(--muted)", fontSize: 12 }}>
          — 한 줄에 하나. <span className="mono">제목 | 태그</span> 형식이면 스마트 컬렉션
          (예: <span className="mono">Tops | category:tops</span> — ListPilot 상품이 자동으로 들어갑니다)
        </span>
        <textarea
          value={collectionsText}
          onChange={(e) => setCollectionsText(e.target.value)}
          rows={4}
          placeholder={"Braiding Hair | category:braiding-hair\nCrochet Hair | category:crochet-hair\nNew Arrivals | promo:new-arrival"}
          className="mono"
          style={{ width: "100%", fontSize: 12, margin: "8px 0" }}
        />
        <button
          className="ghost"
          onClick={() => void runCollections()}
          disabled={collectionsBusy || !collectionsText.trim() || !store.connected}
        >
          {collectionsBusy ? "생성 중…" : "컬렉션 생성"}
        </button>
      </div>
    </div>
  );
}
