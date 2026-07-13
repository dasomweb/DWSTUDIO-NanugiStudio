# --- build ---------------------------------------------------------------
FROM node:20-slim AS builder
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# NEXT_PUBLIC_* 은 런타임이 아니라 빌드 시점에 번들에 박힌다.
# Railway 에서 이 값을 빌드 변수로 넘겨야 관리자 페이지가 API 를 찾는다.
ARG NEXT_PUBLIC_API_BASE
ENV NEXT_PUBLIC_API_BASE=${NEXT_PUBLIC_API_BASE}

RUN npm run build

# --- run -----------------------------------------------------------------
FROM node:20-slim AS runner
WORKDIR /app
ENV NODE_ENV=production

# standalone 번들은 node_modules 를 통째로 들고 오지 않는다.
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

# standalone server.js 는 HOSTNAME 이 없으면 localhost 에만 바인딩한다 →
# 컨테이너 밖에서 접근이 안 된다. 0.0.0.0 을 명시해야 한다.
ENV HOSTNAME=0.0.0.0
ENV PORT=3000
EXPOSE 3000
CMD ["sh", "-c", "node server.js"]
