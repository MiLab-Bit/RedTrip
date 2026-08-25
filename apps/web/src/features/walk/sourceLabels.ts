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
