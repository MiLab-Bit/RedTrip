import type { SourceRef } from "@redtrip/contracts";

const DATASET_LABEL: Record<string, string> = {
  building_detail: "建筑详情",
  "building_detail.relation": "人物关系",
  "building_detail.event": "建筑附带事件",
  event_list: "事件记载",
  "fixture/demo": "演示核录",
  "R-20 whitelist": "R-20 白名单",
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

/** L1 证据通道统一标签（Web / 小程序共用文案） */
export function channelLabel(channel: string | null | undefined): string {
  switch (channel) {
    case "slc":
      return "上图馆藏";
    case "landmark":
      return "策展词库";
    case "osm":
      return "OSM 坐标";
    case "amap":
      return "地图核录";
    case "manual":
      return "地名志";
    default:
      return channel ? String(channel) : "未标注";
  }
}

export function channelBadgeClass(channel: string | null | undefined): string {
  const c = channel || "unknown";
  return `channel-badge is-${c}`;
}
