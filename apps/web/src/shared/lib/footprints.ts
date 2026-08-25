import type { RouteEnvelope } from "@redtrip/contracts";
import type { FootprintFeature } from "../../features/map/Footprints";
import { API_BASE } from "./apiBase";

export type FootprintBundle = {
  features: FootprintFeature[];
  note: string;
  source?: string;
  live?: boolean;
};

const cache = new Map<string, FootprintBundle>();

function pointsKey(
  points: Array<{ lat: number; lng: number }>,
): string {
  return points
    .map((p) => `${p.lat.toFixed(5)},${p.lng.toFixed(5)}`)
    .join("|");
}

function noteFor(
  count: number,
  source?: string,
  error?: string,
): string {
  if (count === 0) {
    return error
      ? `OSM 暂不可用（${error.slice(0, 48)}）· 显示策展意象建筑`
      : "走廊暂无 OSM 轮廓 · 显示策展意象建筑";
  }
  if (source?.startsWith("fixture")) {
    return `走廊缓存 footprint ×${count} · Overpass 旁路 · 高度缺省处为示意`;
  }
  return `OSM footprint ×${count} · 已拉取 · 高度缺省处为示意`;
}

export async function fetchFootprints(
  envelope: RouteEnvelope,
  signal?: AbortSignal,
): Promise<FootprintBundle> {
  const points = envelope.route.stops.map((s) => ({
    lat: s.geo.lat,
    lng: s.geo.lng,
  }));
  const key = pointsKey(points);
  const hit = cache.get(key);
  if (hit) return hit;

  try {
    const res = await fetch(`${API_BASE}/v1/map/footprints`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ points }),
      signal,
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = (await res.json()) as {
      features?: FootprintFeature[];
      error?: string;
      source?: string;
      live?: boolean;
      count?: number;
    };
    const feats = data.features ?? [];
    const bundle: FootprintBundle = {
      features: feats,
      note: noteFor(feats.length, data.source, data.error),
      source: data.source,
      live: data.live,
    };
    if (feats.length > 0) cache.set(key, bundle);
    return bundle;
  } catch {
    if (signal?.aborted) {
      return { features: [], note: "OSM 拉取已取消" };
    }
    return {
      features: [],
      note: "OSM 拉取失败 · 显示策展意象建筑（坐标仍真实落位）",
    };
  }
}
