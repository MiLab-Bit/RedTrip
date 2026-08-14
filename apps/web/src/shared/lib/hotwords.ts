import { API_BASE } from "./apiBase";

export type HotPlaceRank = {
  rank: number;
  place: string;
  scene: string;
  heat: number;
  score: number;
  mentions: number;
  top_term: string;
  terms: string[];
};

export type HotwordsRanking = {
  week: string;
  updated_at?: string | null;
  source?: string;
  label?: string;
  count: number;
  items: HotPlaceRank[];
};

export async function fetchHotwordsRanking(
  topK = 10,
): Promise<HotwordsRanking> {
  const res = await fetch(`${API_BASE}/v1/hotwords/ranking?top_k=${topK}`);
  if (!res.ok) {
    throw new Error(`热词榜 HTTP ${res.status}`);
  }
  const json = (await res.json()) as HotwordsRanking;
  if (!json?.items?.length) {
    throw new Error("热词榜为空");
  }
  return json;
}
