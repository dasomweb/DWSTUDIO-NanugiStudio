/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Railway 컨테이너용 — 런타임에 필요한 파일만 추린 standalone 번들을 만든다.
  output: "standalone",
};

export default nextConfig;
