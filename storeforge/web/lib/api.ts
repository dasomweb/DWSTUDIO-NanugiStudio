"use client";

/** StoreForge API 클라이언트. 토큰은 localStorage 에 둔다 (내부 관리자 도구). */

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8787";

const TOKEN_KEY = "storeforge.token";
const USER_KEY = "storeforge.user";

export type Role = "superadmin" | "admin" | "owner";

export type User = {
  id: number;
  email: string;
  name: string;
  role: Role;
  is_active: boolean;
};

export type AuthType = "client_credentials" | "token";

export type Store = {
  id: number;
  name: string;
  shop_domain: string;
  auth_type: AuthType;
  connected: boolean;
  shop_name: string | null;
  shop_plan: string | null;
  last_checked_at: string | null;
  last_error: string | null;
  granted_scopes: string[];
  missing_scopes: string[];
  required_scopes: string[];
  recommended_scopes: string[];
  has_credentials: boolean;
};

/** 자격증명. auth_type 에 따라 필요한 필드가 다르다. 비밀값은 응답에 절대 실리지 않는다. */
export type Credentials = {
  auth_type: AuthType;
  client_id?: string;
  client_secret?: string;
  access_token?: string;
};

export type Run = {
  id: number;
  store_id: number;
  status: "pending" | "running" | "succeeded" | "failed";
  error: string | null;
  started_at: string;
  finished_at: string | null;
};

export type Font = {
  handle: string;
  family: string;
  category: string;
  korean: boolean;
  weights: number[];
};

export type BrandInput = {
  primary: string;
  background: string;
  foreground: string;
  accent?: string | null;
  body_font: string;
  heading_font: string;
  subheading_font: string;
  accent_font: string;
  page_width: "narrow" | "medium" | "wide";
};

export type SchemeAudit = {
  id: string;
  role: string;
  pass: boolean;
  checks: Record<string, { ratio: number; target: number; pass: boolean }>;
};

export type Preview = {
  payload: {
    v: number;
    root: Record<string, string>;
    schemes: { id: string; css: Record<string, string> }[];
    font_faces: { family: string; weight: number; style: string; asset: string }[];
    layout: { page_width: string };
  };
  report: { wcag_pass: boolean; value_count: number; schemes: SchemeAudit[] };
};

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function getUser(): User | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(USER_KEY);
  return raw ? (JSON.parse(raw) as User) : null;
}

export function setSession(token: string, user: User) {
  window.localStorage.setItem(TOKEN_KEY, token);
  window.localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearSession() {
  window.localStorage.removeItem(TOKEN_KEY);
  window.localStorage.removeItem(USER_KEY);
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken();
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "content-type": "application/json",
      ...(token ? { authorization: `Bearer ${token}` } : {}),
      ...(init.headers ?? {}),
    },
  });

  // 401 은 보통 '세션 만료'지만, 로그인 요청의 401 은 '비밀번호 틀림'이다.
  // 여기서 리다이렉트하면 오류 메시지가 화면에 뜨지 못하고 로그인 폼만 다시 그려진다.
  const isLogin = path === "/auth/login";
  if (res.status === 401 && !isLogin && typeof window !== "undefined") {
    clearSession();
    window.location.href = "/login";
    throw new ApiError(401, "세션이 만료됐습니다.");
  }

  if (!res.ok) {
    let detail = `요청 실패 (${res.status})`;
    try {
      const body = await res.json();
      // FastAPI 는 문자열 detail 또는 검증 오류 배열을 준다.
      if (typeof body.detail === "string") detail = body.detail;
      else if (Array.isArray(body.detail))
        detail = body.detail
          .map((e: any) => `${(e.loc ?? []).slice(1).join(".")}: ${e.msg}`)
          .join(", ");
    } catch {
      /* 본문 없음 */
    }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  login: (email: string, password: string) =>
    request<{ access_token: string; user: User }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),

  updateProfile: (body: { name?: string; email?: string }) =>
    request<User>("/auth/me", { method: "PATCH", body: JSON.stringify(body) }),
  changePassword: (current_password: string, new_password: string) =>
    request<{ access_token: string; user: User }>("/auth/me/password", {
      method: "POST",
      body: JSON.stringify({ current_password, new_password }),
    }),
  resetUserPassword: (id: number, new_password: string) =>
    request<void>(`/auth/users/${id}/password`, {
      method: "PUT",
      body: JSON.stringify({ new_password }),
    }),

  listUsers: () => request<User[]>("/auth/users"),
  createUser: (body: {
    email: string;
    name: string;
    password: string;
    role: Role;
    store_ids: number[];
  }) => request<User>("/auth/users", { method: "POST", body: JSON.stringify(body) }),
  deactivateUser: (id: number) =>
    request<void>(`/auth/users/${id}`, { method: "DELETE" }),

  listStores: () => request<Store[]>("/stores"),
  createStore: (body: { name: string; shop_domain: string } & Credentials) =>
    request<Store>("/stores", { method: "POST", body: JSON.stringify(body) }),
  testStore: (id: number) => request<Store>(`/stores/${id}/test`, { method: "POST" }),
  updateCredentials: (id: number, creds: Credentials) =>
    request<Store>(`/stores/${id}/credentials`, {
      method: "PUT",
      body: JSON.stringify(creds),
    }),
  deleteStore: (id: number) => request<void>(`/stores/${id}`, { method: "DELETE" }),
  listMembers: (id: number) => request<User[]>(`/stores/${id}/members`),
  addMember: (storeId: number, userId: number) =>
    request<void>(`/stores/${storeId}/members/${userId}`, { method: "POST" }),

  listFonts: () => request<Font[]>("/fonts"),
  interpret: (description: string) =>
    request<{ brand: BrandInput; rationale: string; report: Preview["report"] }>(
      "/interpret",
      { method: "POST", body: JSON.stringify({ description }) },
    ),
  preview: (brand: BrandInput) =>
    request<Preview>("/preview", { method: "POST", body: JSON.stringify(brand) }),
  currentBrand: (storeId: number) =>
    request<{ applied: boolean; metafield: any }>(`/stores/${storeId}/brand`),
  apply: (storeId: number, brand: BrandInput, force: boolean) =>
    request<Run>(`/stores/${storeId}/apply`, {
      method: "POST",
      body: JSON.stringify({ brand, force }),
    }),
  listRuns: (storeId: number) => request<Run[]>(`/stores/${storeId}/runs`),
};
