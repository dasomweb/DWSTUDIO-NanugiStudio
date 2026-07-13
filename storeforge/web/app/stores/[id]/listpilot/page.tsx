"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import Shell from "@/components/Shell";
import {
  api,
  ApiError,
  type Listing,
  type ListingVariant,
  type Store,
} from "@/lib/api";

const STATUS_LABEL: Record<Listing["status"], string> = {
  draft: "초안",
  pushed: "등록됨",
  failed: "실패",
};

/** 변형 한 줄. 가격·재고는 등록 전에 여기서 고친다 (도매 표의 원가가 그대로 판매가일 리 없다). */
function VariantRow({
  variant,
  onChange,
}: {
  variant: ListingVariant;
  onChange: (v: ListingVariant) => void;
}) {
  return (
    <tr>
      <td className="mono" style={{ color: "var(--muted)" }}>
        {variant.option_name}: {variant.option_value}
      </td>
      <td>
        <input
          type="number"
          step="0.01"
          value={variant.price ?? ""}
          onChange={(e) =>
            onChange({
              ...variant,
              price: e.target.value === "" ? null : Number(e.target.value),
            })
          }
          style={{ width: 90 }}
        />
      </td>
      <td>
        <input
          value={variant.sku ?? ""}
          onChange={(e) => onChange({ ...variant, sku: e.target.value || null })}
          style={{ width: 110 }}
        />
      </td>
      <td>
        <input
          type="number"
          value={variant.quantity}
          onChange={(e) => onChange({ ...variant, quantity: Number(e.target.value) })}
          style={{ width: 70 }}
        />
      </td>
    </tr>
  );
}

function ListingCard({
  storeId,
  listing,
  onChanged,
  onError,
}: {
  storeId: number;
  listing: Listing;
  onChanged: (l: Listing | null) => void;
  onError: (msg: string) => void;
}) {
  const [draft, setDraft] = useState(listing);
  const [busy, setBusy] = useState<string | null>(null);
  const dirty = JSON.stringify(draft) !== JSON.stringify(listing);

  useEffect(() => setDraft(listing), [listing]);

  const run = async (label: string, fn: () => Promise<Listing | null>) => {
    setBusy(label);
    onError("");
    try {
      onChanged(await fn());
    } catch (err) {
      onError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  };

  const save = () =>
    run("저장", () =>
      api.updateListing(storeId, listing.id, {
        title: draft.title,
        body_html: draft.body_html,
        vendor: draft.vendor,
        product_type: draft.product_type,
        tags: draft.tags,
        variants: draft.variants,
      })
    );

  return (
    <div className="card" style={{ marginBottom: 14 }}>
      <div style={{ display: "flex", gap: 10, alignItems: "center", marginBottom: 10 }}>
        <input
          value={draft.title}
          onChange={(e) => setDraft({ ...draft, title: e.target.value })}
          style={{ flex: 1, fontWeight: 600 }}
        />
        <span className={`pill${listing.status === "pushed" ? " ok" : listing.status === "failed" ? " bad" : ""}`}>
          {STATUS_LABEL[listing.status]}
        </span>
        {listing.confidence != null && (
          <span className="pill" title="AI 추출 신뢰도">
            {Math.round(listing.confidence * 100)}%
          </span>
        )}
        {listing.image_count > 0 && <span className="pill">이미지 {listing.image_count}</span>}
      </div>

      <div style={{ display: "flex", gap: 8, marginBottom: 10 }}>
        <input
          placeholder="브랜드"
          value={draft.vendor ?? ""}
          onChange={(e) => setDraft({ ...draft, vendor: e.target.value || null })}
        />
        <input
          placeholder="상품 타입"
          value={draft.product_type ?? ""}
          onChange={(e) => setDraft({ ...draft, product_type: e.target.value || null })}
        />
        <input
          placeholder="태그 (콤마 구분)"
          value={draft.tags.join(",")}
          onChange={(e) =>
            setDraft({
              ...draft,
              tags: e.target.value.split(",").map((t) => t.trim()).filter(Boolean),
            })
          }
          style={{ flex: 1 }}
        />
      </div>

      <table className="table" style={{ marginBottom: 10 }}>
        <thead>
          <tr>
            <th>변형</th>
            <th>가격</th>
            <th>SKU</th>
            <th>재고</th>
          </tr>
        </thead>
        <tbody>
          {draft.variants.map((v, i) => (
            <VariantRow
              key={i}
              variant={v}
              onChange={(nv) =>
                setDraft({
                  ...draft,
                  variants: draft.variants.map((x, j) => (i === j ? nv : x)),
                })
              }
            />
          ))}
        </tbody>
      </table>

      {listing.error && (
        <div className="err" style={{ marginBottom: 10 }}>
          {listing.error}
        </div>
      )}

      <div style={{ display: "flex", gap: 8 }}>
        <button onClick={save} disabled={!dirty || busy !== null}>
          {busy === "저장" ? "저장 중…" : "저장"}
        </button>
        <button
          className="ghost"
          disabled={busy !== null}
          onClick={() => run("설명", () => api.describeListing(storeId, listing.id))}
        >
          {busy === "설명" ? "생성 중…" : "AI 상세설명"}
        </button>
        <button
          disabled={busy !== null || dirty}
          title={dirty ? "먼저 저장하세요" : "Shopify 에 draft 상태로 등록합니다"}
          onClick={() => run("등록", () => api.pushListing(storeId, listing.id))}
        >
          {busy === "등록" ? "등록 중…" : listing.status === "pushed" ? "다시 등록" : "Shopify 등록"}
        </button>
        <button
          className="ghost"
          style={{ marginLeft: "auto" }}
          disabled={busy !== null}
          onClick={() =>
            run("삭제", async () => {
              await api.deleteListing(storeId, listing.id);
              return null;
            })
          }
        >
          삭제
        </button>
      </div>
    </div>
  );
}

export default function ListPilotPage() {
  const params = useParams<{ id: string }>();
  const storeId = Number(params.id);

  const [store, setStore] = useState<Store | null>(null);
  const [listings, setListings] = useState<Listing[]>([]);
  const [industries, setIndustries] = useState<string[]>([]);
  const [industry, setIndustry] = useState("fashion");
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    try {
      const [stores, ls, ind] = await Promise.all([
        api.listStores(),
        api.listListings(storeId),
        api.listIndustries(),
      ]);
      setStore(stores.find((s) => s.id === storeId) ?? null);
      setListings(ls);
      setIndustries(ind.industries);
      setIndustry(ind.default);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    }
  }, [storeId]);

  useEffect(() => {
    void load();
  }, [load]);

  async function upload(file: File) {
    setUploading(true);
    setError("");
    setOk("");
    try {
      const created = await api.extractListings(storeId, file, industry);
      setListings((prev) => [...created, ...prev]);
      setOk(`${created.length}개 상품 초안을 추출했습니다. 검수 후 등록하세요.`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  const blocked = store?.blocked_modules.includes("listpilot");
  const off = store && !store.enabled_modules.includes("listpilot");

  return (
    <Shell>
      <h1>ListPilot</h1>
      <p style={{ color: "var(--muted)", marginTop: -6 }}>
        {store?.name} · 상품 원본(사진·인보이스·엑셀) → AI 초안 → 검수 → Shopify 등록
      </p>

      {off && (
        <div className="err">
          이 스토어에서 ListPilot 모듈이 꺼져 있습니다.{" "}
          <Link href={`/stores/${storeId}`}>스토어 설정</Link>에서 켜세요.
        </div>
      )}
      {blocked && (
        <div className="err">
          스코프가 모자랍니다: <span className="mono">{store?.missing_scopes.join(", ")}</span>
        </div>
      )}
      {error && <div className="err">{error}</div>}
      {ok && <div className="ok">{ok}</div>}

      <div className="card" style={{ marginBottom: 20 }}>
        <h2 style={{ marginTop: 0 }}>원본 업로드</h2>
        <p style={{ color: "var(--muted)", fontSize: 13 }}>
          상품 사진 · 도매 인보이스(PDF) · 상품 목록(엑셀/CSV). 인보이스 한 장에서 여러 상품이
          나옵니다. <strong>등록은 자동으로 하지 않습니다</strong> — 검수 후 직접 누르세요.
        </p>

        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <select value={industry} onChange={(e) => setIndustry(e.target.value)}>
            {industries.map((i) => (
              <option key={i} value={i}>
                {i}
              </option>
            ))}
          </select>
          <input
            ref={fileRef}
            type="file"
            accept="image/*,.pdf,.csv,.xlsx,.xls"
            disabled={uploading || off || blocked}
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) void upload(f);
            }}
          />
          {uploading && <span style={{ color: "var(--muted)" }}>추출 중… (AI 가 읽는 중)</span>}
        </div>
      </div>

      <h2>초안 {listings.length > 0 && `(${listings.length})`}</h2>
      {listings.length === 0 && (
        <p style={{ color: "var(--muted)" }}>아직 없습니다. 파일을 업로드하세요.</p>
      )}
      {listings.map((l) => (
        <ListingCard
          key={l.id}
          storeId={storeId}
          listing={l}
          onError={setError}
          onChanged={(updated) =>
            setListings((prev) =>
              updated
                ? prev.map((x) => (x.id === updated.id ? updated : x))
                : prev.filter((x) => x.id !== l.id)
            )
          }
        />
      ))}
    </Shell>
  );
}
