"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import Link from "next/link";
import { clearSession, getToken, getUser, type User } from "@/lib/api";

const ROLE_LABEL: Record<string, string> = {
  superadmin: "슈퍼어드민",
  admin: "어드민",
  owner: "오너",
};

/** 로그인 게이트 + 사이드 네비. 인증이 없으면 /login 으로 보낸다. */
export default function Shell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    setUser(getUser());
  }, [router]);

  if (!user) return null;

  const logout = () => {
    clearSession();
    router.replace("/login");
  };

  const link = (href: string, label: string) => (
    <Link
      href={href}
      className={`navlink${pathname.startsWith(href) ? " active" : ""}`}
    >
      {label}
    </Link>
  );

  return (
    <div className="shell">
      <aside className="side">
        <div className="brandmark">StoreForge</div>
        <div className="brandsub">DASOMWEB · 나누기 테마</div>

        {link("/stores", "스토어")}
        {/* 사용자 관리는 슈퍼어드민 전용 — API 도 403 으로 막지만 메뉴부터 숨긴다 */}
        {user.role === "superadmin" && link("/users", "사용자")}
        {link("/account", "계정")}

        <div style={{ marginTop: 24, paddingTop: 16, borderTop: "1px solid var(--line)" }}>
          <div style={{ fontSize: 12, marginBottom: 2 }}>{user.email}</div>
          <div className="pill" style={{ marginBottom: 10 }}>
            {ROLE_LABEL[user.role] ?? user.role}
          </div>
          <button className="ghost" style={{ width: "100%" }} onClick={logout}>
            로그아웃
          </button>
        </div>
      </aside>

      <main className="main">{children}</main>
    </div>
  );
}
