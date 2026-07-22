import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "StoreForge — 스토어 온보딩 자동화",
  description: "DASOMWEB · AI 기반 Shopify 스토어 온보딩",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
