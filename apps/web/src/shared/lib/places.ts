import { API_BASE } from "./apiBase";

export type PlaceSuggestItem = {
  id: string;
  label: string;
  scene: string;
  source: "whitelist" | "corridor" | "hotwords" | string;
  source_label: string;
  district?: string;
  heat?: number;
  hint?: string;
};

export type PlaceSuggestResponse = {
  q: string;
  mode: "browse" | "search" | string;
  count: number;
  items: PlaceSuggestItem[];
  sources: string[];
};

export async function suggestPlaces(
  q: string,
  limit = 8,
): Promise<PlaceSuggestResponse> {
  const params = new URLSearchParams({
    q,
    limit: String(limit),
  });
  const res = await fetch(`${API_BASE}/v1/places/suggest?${params}`);
  if (!res.ok) {
    throw new Error(`地点联想 HTTP ${res.status}`);
  }
  return (await res.json()) as PlaceSuggestResponse;
}
