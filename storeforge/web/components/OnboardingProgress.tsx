"use client";

import { useCallback, useEffect, useState } from "react";
import {
  api,
  ApiError,
  type BrandInput,
  type Checklist,
  type Store,
} from "@/lib/api";

type StepStatus = "running" | "ok" | "fail" | "skip";
type LogLine = { label: string; status: StepStatus; msg?: string };

/**
 * 온보딩 진행률 + 남은 단계 전체 실행.
 *
 * 체크리스트는 화면의 성공 메시지가 아니라 **Shopify 실상태**를 읽은 판정이다
 * (UAT 교훈 — 성공 표시와 실제 반영은 다를 수 있다).
 *
 * 전체 실행은 "남은 것만" 돌린다: 이미 완료된 항목은 건드리지 않으므로 몇 번을
 * 눌러도 안전하다. 정책(법적 검토 필요)과 컬렉션(입력 필요)은 자동화하지 않는다.
 */
export default function OnboardingProgress({
  store,
  brand,
  description,
  layoutId,
  onChanged,
}: {
  store: Store;
  brand: BrandInput;
  description: string;
  layoutId: string;
  onChanged?: () => void;
}) {
  const [checklist, setChecklist] = useState<Checklist | null>(null);
  const [running, setRunning] = useState(false);
  const [log, setLog] = useState<LogLine[]>([]);

  const refresh = useCallback(async () => {
    try {
      setChecklist(await api.checklist(store.id));
    } catch {
      setChecklist(null);
    }
  }, [store.id]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const doneOf = (key: string) =>
    checklist?.items.find((i) => i.key === key)?.done ?? false;

  async function runAll() {
    if (!checklist) return;
    setRunning(true);
    setLog([]);

    const push = (line: LogLine) => setLog((prev) => [...prev, line]);
    const update = (status: StepStatus, msg?: string) =>
      setLog((prev) => prev.map((l, i) => (i === prev.length - 1 ? { ...l, status, msg } : l)));

    type Step = { label: string; skip?: string; run: () => Promise<string> };
    const steps: Step[] = [
      {
        label: "홈 구성 반영",
        skip: !layoutId ? "2단계에서 홈 구성을 먼저 고르세요" : undefined,
        run: async () => {
          const r = await api.applyLayout(store.id, layoutId);
          return `${r.applied} (섹션 ${r.sections.length}개)`;
        },
      },
      {
        label: "색·폰트 주입",
        skip: doneOf("brand") ? "이미 주입됨 — 바꾸려면 4단계에서 덮어쓰기" : undefined,
        run: async () => {
          await api.apply(store.id, brand, false);
          return "주입 완료";
        },
      },
      {
        label: "히어로 이미지 (PC·모바일)",
        skip: doneOf("hero") ? "이미 반영됨 — 다시 만들려면 4단계에서" : undefined,
        run: async () => {
          await api.heroImages(store.id, {
            description,
            primary: brand.primary,
            background: brand.background,
            accent: brand.accent ?? brand.primary,
          });
          return "생성·반영 완료";
        },
      },
      {
        label: "페이지 4종 생성·발행",
        skip: doneOf("pages")
          ? "이미 있음"
          : !description.trim()
            ? "1단계 브랜드 설명이 필요합니다"
            : undefined,
        run: async () => {
          const d = await api.draftPages(store.id, {
            description,
            page_kinds: ["about", "contact", "faq", "shipping-info"],
            policy_types: [],
          });
          const r = await api.applyPages(store.id, {
            pages: d.pages,
            publish: true,
            policies: [],
            policies_reviewed: false,
          });
          return r.pages.map((p) => p.handle).join(", ");
        },
      },
      {
        label: "메뉴 구성",
        skip: doneOf("menu") ? "이미 구성됨 — 바꾸려면 6단계에서" : undefined,
        run: async () => {
          const p = await api.navPreview(store.id);
          const r = await api.navApply(store.id, { header: p.header, footer: p.footer });
          return r.applied.join(", ");
        },
      },
    ];

    for (const step of steps) {
      if (step.skip) {
        push({ label: step.label, status: "skip", msg: step.skip });
        continue;
      }
      push({ label: step.label, status: "running" });
      try {
        update("ok", await step.run());
      } catch (err) {
        update("fail", err instanceof ApiError ? err.message : String(err));
        // 실패해도 다음 단계는 계속 — 어디까지 됐는지가 보이는 편이 낫다
      }
    }

    await refresh();
    onChanged?.();
    setRunning(false);
  }

  const ICON: Record<StepStatus, string> = { running: "⏳", ok: "✓", fail: "✗", skip: "―" };

  return (
    <div className="card">
      <div className="row" style={{ alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <h2 style={{ margin: 0, flex: "0 0 auto" }}>온보딩 진행률</h2>
        {checklist ? (
          <>
            <strong>
              {checklist.done_count}/{checklist.total}
            </strong>
            <div
              style={{
                flex: 1, minWidth: 120, height: 8, borderRadius: 4,
                background: "var(--line)", overflow: "hidden",
              }}
            >
              <div
                style={{
                  width: `${(checklist.done_count / checklist.total) * 100}%`,
                  height: "100%", background: "var(--ok, #6a9955)",
                }}
              />
            </div>
          </>
        ) : (
          <span style={{ color: "var(--muted)", fontSize: 13 }}>상태 확인 중…</span>
        )}
        <button onClick={() => void runAll()} disabled={running || !checklist || !store.connected}>
          {running ? "실행 중…" : "남은 단계 전체 실행"}
        </button>
        <button className="ghost" onClick={() => void refresh()} disabled={running}>
          새로 판정
        </button>
      </div>

      {checklist && (
        <div className="row" style={{ marginTop: 10, gap: 6, flexWrap: "wrap" }}>
          {checklist.items.map((i) => (
            <span
              key={i.key}
              className={`pill${i.done ? " ok" : ""}`}
              title={i.done ? "완료 (Shopify 실상태 기준)" : i.hint}
            >
              {i.done ? "✓" : "○"} {i.label}
            </span>
          ))}
        </div>
      )}

      {log.length > 0 && (
        <div style={{ marginTop: 12, fontSize: 13 }}>
          {log.map((l, i) => (
            <div key={i} style={{ marginBottom: 2 }}>
              {ICON[l.status]} <strong>{l.label}</strong>
              {l.msg && (
                <span style={{ color: l.status === "fail" ? "var(--bad, #d9534f)" : "var(--muted)" }}>
                  {" "}— {l.msg}
                </span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
