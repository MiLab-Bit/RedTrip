import type { SourceRef } from "@redtrip/contracts";

const DATASET_LABEL: Record<string, string> = {
  building_detail: "馆藏建筑",
  "building_detail.relation": "人物关系",
  "building_detail.timeline": "馆藏时间线",
  "building_detail.event": "建筑附带事件",
  event_list: "事件记载",
  "fixture/demo": "演示核录",
  "R-20 whitelist": "R-20 白名单",
  cbdb_classical: "CBDB 历代人物传记",
  cbdb: "CBDB 历代人物传记",
  geonames_corpus: "地名志",
  geonames: "地名志",
  literary_corpus: "文学交集",
  literary: "文学交集",
  souyun_poem: "搜韵诗词",
  road_corpus: "路名志",
  road_list: "路名志",
  "curated.landmark-facts": "历史风貌区词库",
  slc: "上海图书馆",
  slc_building: "上图书目 · 建筑",
  slc_event: "上图事件",
  slc_person: "上图人物",
  slc_era: "纪年",
  slc_poem: "诗词",
  amap: "高德 POI",
  amap_poi: "高德 POI",
  source: "外部来源",
};

export function datasetLabel(dataset: string): string {
  return DATASET_LABEL[dataset] ?? dataset;
}

export function kindLabel(kind: string): string {
  switch (kind) {
    case "event":
      return "事件";
    case "person":
      return "人物";
    case "building":
      return "建筑";
    case "era":
      return "年代";
    case "poem":
      return "诗文";
    case "geoname":
      return "地名";
    case "literary":
      return "文史";
    case "classical":
      return "典籍";
    default:
      return kind;
  }
}

/** Short id for UI — never dominate the layout with full URI. */
export function shortRecordId(recordId: string): string {
  if (recordId.startsWith("http")) {
    const parts = recordId.replace(/\/$/, "").split("/");
    return parts[parts.length - 1] || recordId.slice(-12);
  }
  if (recordId.length > 28) return recordId.slice(0, 14) + "…" + recordId.slice(-8);
  return recordId;
}

export function sourceHeadline(source: SourceRef): string {
  return datasetLabel(source.dataset);
}

/** CBDB 人物记录回查 URL（典籍溯源链外链） */
export function cbdbRecordUrl(recordId: string): string | null {
  // record_id 形如 cbdb:616847 或纯 616847
  const m = recordId.match(/(\d+)$/);
  if (!m) return null;
  return `https://cbdb.fas.harvard.edu/cbdbapi/person.php?id=${m[1]}&o=db`;
}

/** 是否为典籍（CBDB）来源 */
export function isClassicalSource(dataset: string): boolean {
  return dataset === "cbdb_classical" || dataset === "cbdb" || /cbdb/i.test(dataset);
}

