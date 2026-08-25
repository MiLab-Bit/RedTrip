import { API_BASE } from "./authConfig";
import { useAuthStore } from "../../features/auth/authStore";

/**
 * 带 Bearer 的鉴权请求：自动注入 access token；
 * 遇 401 时用 refresh token 静默续期并重试一次。
 * 用于需要登录态的资源请求（如将来调用 /v1/me 刷新资料）。
 */
/** 供策展等非 React 模块注入 Bearer（BYOK 走用户 active provider）。 */
export function authHeaders(extra?: HeadersInit): Headers {
  const headers = new Headers(extra);
  if (!headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const token = useAuthStore.getState().accessToken;
  if (token) headers.set("Authorization", `Bearer ${token}`);
  return headers;
}

export async function authedFetch(
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  const headers = new Headers(init.headers);
  const token = useAuthStore.getState().accessToken;
  if (token) headers.set("Authorization", `Bearer ${token}`);

  let res = await fetch(API_BASE + path, { ...init, headers });
  if (res.status === 401) {
    const ok = await useAuthStore.getState().refresh();
    if (ok) {
      const next = useAuthStore.getState().accessToken;
      if (next) headers.set("Authorization", `Bearer ${next}`);
      res = await fetch(API_BASE + path, { ...init, headers });
    }
  }
  return res;
}

export async function fetchMe(): Promise<unknown> {
  const res = await authedFetch("/me");
  if (!res.ok) throw new Error(`获取资料失败 (${res.status})`);
  return res.json();
}

// ── 用户自带大模型供应商密钥（模型配置）──
export interface ProviderPreset {
  provider: string;
  label: string;
  baseUrl: string;
  defaultModel: string;
}

export interface ModelProvider {
  id: string;
  name: string;
  provider: string;
  base_url: string | null;
  model: string | null;
  slot: "text" | "multimodal";
  status: "unverified" | "active" | "error";
  last_error: string | null;
  last_tested_at: string | null;
  created_at: string;
}

export async function listProviderPresets(): Promise<ProviderPreset[]> {
  const res = await fetch(API_BASE + "/model-providers/presets");
  if (!res.ok) throw new Error(`获取供应商列表失败 (${res.status})`);
  const j = (await res.json()) as { providers?: ProviderPreset[] };
  return j.providers ?? [];
}

export async function listModelProviders(): Promise<ModelProvider[]> {
  const res = await authedFetch("/model-providers");
  if (!res.ok) throw new Error(`获取配置失败 (${res.status})`);
  const j = (await res.json()) as { providers?: ModelProvider[] };
  return j.providers ?? [];
}

export async function testProvider(input: {
  provider: string;
  apiKey: string;
  baseUrl?: string;
  model?: string;
}): Promise<{ ok: boolean; latency_ms: number; error?: string; model?: string }> {
  const res = await authedFetch("/model-providers/test", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!res.ok) throw new Error(`测试失败 (${res.status})`);
  return res.json();
}

export async function createModelProvider(input: {
  name: string;
  provider: string;
  apiKey: string;
  baseUrl?: string;
  model?: string;
  slot?: "text" | "multimodal";
}): Promise<{ provider: ModelProvider; test: { ok: boolean; error?: string } }> {
  const res = await authedFetch("/model-providers", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!res.ok) throw new Error(`保存失败 (${res.status})`);
  return res.json();
}

export async function deleteModelProvider(id: string): Promise<void> {
  const res = await authedFetch(`/model-providers/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`删除失败 (${res.status})`);
}
