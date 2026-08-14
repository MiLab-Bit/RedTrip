/**
 * 城市选择器数据源（前端主页「在哪个城市走」）。
 *
 * 优先拉后端 /v1/cities（含 OSM 语料就绪标记 ready）；失败则回退静态列表，
 * 保证 UI 永远可渲染。ready=false 的城市（OSM 语料尚未拉取）在选项上禁用并标注。
 */
import { API_BASE } from "./apiBase";

export interface CityInfo {
  key: string;
  name_zh: string;
  center: { lat: number; lng: number };
  partners: string[];
  ready: boolean;
}

/** 静态兜底（与后端 CITY_REGISTRY 同义，仅作离线回退）。ready 缺省视为可用。 */
export const STATIC_CITIES: CityInfo[] = [
  { key: "shanghai", name_zh: "上海", center: { lat: 31.2304, lng: 121.4737 }, partners: ["slc"], ready: true },
  { key: "beijing", name_zh: "北京", center: { lat: 39.9042, lng: 116.4074 }, partners: ["cbdb"], ready: true },
  { key: "suzhou", name_zh: "苏州", center: { lat: 31.2989, lng: 120.5853 }, partners: ["suzhou_lib"], ready: true },
  { key: "nanjing", name_zh: "南京", center: { lat: 32.0603, lng: 118.7969 }, partners: ["nanjing_lib"], ready: true },
  { key: "hangzhou", name_zh: "杭州", center: { lat: 30.2741, lng: 120.1551 }, partners: ["zhejiang_lib"], ready: true },
  { key: "jiaxing", name_zh: "嘉兴", center: { lat: 30.7524, lng: 120.75 }, partners: ["jiaxing_lib"], ready: true },
  { key: "yangzhou", name_zh: "扬州", center: { lat: 32.3941, lng: 119.4145 }, partners: ["yangzhou_lib"], ready: true },
  { key: "shenzhen", name_zh: "深圳", center: { lat: 22.5431, lng: 114.0579 }, partners: ["shenzhen_lib"], ready: true },
  { key: "nantong", name_zh: "南通", center: { lat: 31.98, lng: 120.8933 }, partners: ["nantong_lib"], ready: true },
  { key: "guangzhou", name_zh: "广州", center: { lat: 23.1291, lng: 113.2644 }, partners: ["souyun"], ready: true },
  { key: "hefei", name_zh: "合肥·安徽", center: { lat: 31.8206, lng: 117.2272 }, partners: ["anhui_lib"], ready: true },
  { key: "chengdu", name_zh: "成都", center: { lat: 30.5728, lng: 104.0668 }, partners: [], ready: true },
  { key: "xian", name_zh: "西安", center: { lat: 34.3416, lng: 108.9398 }, partners: [], ready: true },
  { key: "chongqing", name_zh: "重庆", center: { lat: 29.563, lng: 106.5516 }, partners: [], ready: true },
];

export const DEFAULT_CITY = "shanghai";

export async function fetchCities(signal?: AbortSignal): Promise<CityInfo[]> {
  try {
    const res = await fetch(`${API_BASE}/v1/cities`, { signal });
    if (!res.ok) throw new Error(`cities HTTP ${res.status}`);
    const json = (await res.json()) as {
      cities?: CityInfo[];
      default?: string;
    };
    if (Array.isArray(json.cities) && json.cities.length) {
      return json.cities;
    }
    throw new Error("empty cities");
  } catch {
    return STATIC_CITIES;
  }
}

/** 同步取城市中文名（用于头部标识等即时渲染）。 */
export function cityName(key: string | null | undefined): string {
  const k = key || DEFAULT_CITY;
  return STATIC_CITIES.find((c) => c.key === k)?.name_zh ?? "上海";
}
