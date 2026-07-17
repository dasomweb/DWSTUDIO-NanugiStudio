"use client";

import type { Store } from "@/lib/api";

/**
 * 수동 설정 체크리스트 — Shopify 가 API 를 열어놓지 않아 StoreForge 가 대신 못 하는 것들.
 *
 * 자동화가 안 되는 이유를 숨기지 않고 명시한다. "여기 없는 건 자동으로 됐다"는 신뢰가
 * 이 목록의 존재 이유다. 항목마다 해당 스토어 관리자 화면으로 바로 가는 링크를 단다.
 */
export default function ManualChecklist({ store }: { store: Store }) {
  const handle = store.shop_domain.replace(".myshopify.com", "");
  const admin = `https://admin.shopify.com/store/${handle}`;

  const items: { title: string; why: string; href: string; menu: string }[] = [
    {
      title: "스토어 기본 정보 — 통화 · 주소 · 타임존 · 단위",
      why: "Shop 기본 설정은 쓰기 API 가 없습니다.",
      href: `${admin}/settings/general`,
      menu: "설정 → 일반",
    },
    {
      title: "결제 설정 — PG · Shopify Payments · 수동 결제",
      why: "결제 공급자 연결은 보안상 관리자에서만 됩니다.",
      href: `${admin}/settings/payments`,
      menu: "설정 → 결제",
    },
    {
      title: "상자(패키지) 사이즈 — 저장된 패키지",
      why: "배송 요금·구간과 달리 패키지 정의는 공개 API 가 없습니다.",
      href: `${admin}/settings/shipping`,
      menu: "설정 → 배송 및 배달 → 패키지",
    },
    {
      title: "정책 자동 관리 끄기 (정책 반영 전 필수)",
      why: "Shopify 가 정책을 자동 관리 중이면 StoreForge 가 정책을 쓸 수 없습니다 — 항목별로 자동 관리를 꺼야 합니다.",
      href: `${admin}/settings/legal`,
      menu: "설정 → 정책",
    },
    {
      title: "세금 설정",
      why: "국가별 세금 등록은 관리자에서만 됩니다.",
      href: `${admin}/settings/taxes`,
      menu: "설정 → 세금 및 관세",
    },
    {
      title: "도메인 연결",
      why: "커스텀 도메인 구매·연결은 관리자에서만 됩니다.",
      href: `${admin}/settings/domains`,
      menu: "설정 → 도메인",
    },
    {
      title: "스토어프론트 비밀번호 해제 (오픈 시)",
      why: "유료 플랜 선택과 비밀번호 해제는 관리자에서만 됩니다.",
      href: `${admin}/online_store/preferences`,
      menu: "온라인 스토어 → 환경설정",
    },
  ];

  return (
    <details className="card">
      <summary style={{ cursor: "pointer" }}>
        <strong>📋 수동 설정 체크리스트</strong>{" "}
        <span style={{ color: "var(--muted)", fontSize: 13 }}>
          — Shopify 가 API 를 열어놓지 않아 관리자에서 직접 해야 하는 {items.length}가지
        </span>
      </summary>
      <p className="sub" style={{ fontSize: 12, margin: "10px 0" }}>
        아래 항목은 StoreForge 가 대신할 수 없습니다. 스토어 오픈 전에 하나씩 확인하세요 —
        링크는 이 스토어({store.shop_domain})의 관리자 화면으로 바로 갑니다.
      </p>
      <table>
        <tbody>
          {items.map((it) => (
            <tr key={it.title}>
              <td style={{ width: "45%" }}>
                <a href={it.href} target="_blank" rel="noreferrer">
                  {it.title} ↗
                </a>
                <div style={{ fontSize: 12, color: "var(--muted)" }}>{it.menu}</div>
              </td>
              <td style={{ fontSize: 12, color: "var(--muted)" }}>{it.why}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </details>
  );
}
