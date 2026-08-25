import { describe, it, expect } from "vitest";
import {
  StoryChapterSchema,
  CuratedStorySchema,
  type StoryChapter,
  type CuratedStory,
  type Theme,
  type EvidenceGraph,
  type WalkRoute,
  type StoryEntity,
} from "@redtrip/contracts";

// ---------------------------------------------------------------------------
// 契约漂移回归测试
//
// 历史 bug：后端 artifacts.py 一度以 snake_case 输出章节字段
// （narrative_role / stop_id / evidence_ids / walking_minutes / cast_refs），
// 且 curated_story 写成 evidence_graph；而 TS 契约与前端消费全是 camelCase。
// 这些测试锁定修复后的契约形状，防止后端序列化再次漂回 snake_case。
// ---------------------------------------------------------------------------

const validChapter: StoryChapter = {
  id: "c1",
  index: 0,
  title: "起点",
  hook: "一句钩子",
  narrativeRole: "Hook",
  stopId: 1,
  relationToPrevious: null,
  evidenceIds: ["f1"],
  walkingMinutes: 5,
  castRefs: ["e1"],
};

const theme: Theme = {
  id: "t1",
  title: "主题",
  open_question: "开放问题？",
  research_axes: [{ axis: "轴", hypothesis: "假设", evidence_cluster_ids: [] }],
  why_visit: "为何造访",
  estimated_duration_min: 90,
  scope_note: "范围说明",
};

const evidenceGraph: EvidenceGraph = {
  theme_id: "t1",
  clusters: [
    {
      id: "cl1",
      dimension: "维度",
      label: "聚类",
      facts: [
        {
          fact_uri: "u1",
          label: "事实",
          assertion: "断言",
          layer: "building",
          source_dataset: "ds",
          confidence: 0.9,
        },
      ],
    },
  ],
  joins: [],
  coverage: {},
};

const cast: StoryEntity[] = [
  { id: "e1", kind: "building", name: "建筑", fact_uri: "u1", note: null },
];

const route: WalkRoute = {
  duration_min: 60,
  walk_meters_est: 1000,
  stops: [
    {
      order: 1,
      whitelist_id: "w1",
      buri: null,
      name: "站点一",
      minutes: 20,
      meaning: "意义",
      transition_to_next: null,
      layers: [
        {
          kind: "building",
          label: "层",
          claim: "主张",
          source: { dataset: "ds", record_id: "r1" },
        },
      ],
      geo: { lat: 31.23, lng: 121.47, coord_source: "manual", precision: "exact" },
      pitfalls: { open_hours: "9-17", enterable: "可", need_reservation: "否" },
    },
    {
      order: 2,
      whitelist_id: "w2",
      buri: null,
      name: "站点二",
      minutes: 20,
      meaning: "意义",
      transition_to_next: null,
      layers: [
        {
          kind: "event",
          label: "层",
          claim: "主张",
          source: { dataset: "ds", record_id: "r2" },
        },
      ],
      geo: { lat: 31.24, lng: 121.48, coord_source: "manual", precision: "approximate" },
      pitfalls: { open_hours: "9-17", enterable: "可", need_reservation: "否" },
    },
    {
      order: 3,
      whitelist_id: "w3",
      buri: null,
      name: "站点三",
      minutes: 20,
      meaning: "意义",
      transition_to_next: null,
      layers: [
        {
          kind: "person",
          label: "层",
          claim: "主张",
          source: { dataset: "ds", record_id: "r3" },
        },
      ],
      geo: { lat: 31.22, lng: 121.46, coord_source: "upstream", precision: "schematic" },
      pitfalls: { open_hours: "9-17", enterable: "可", need_reservation: "否" },
    },
  ],
};

const validStory: CuratedStory = {
  id: "s1",
  theme,
  thesis: "论点",
  cast,
  chapters: [validChapter],
  evidenceGraph,
  route,
};

describe("StoryChapterSchema — 章节字段命名契约", () => {
  it("camelCase 形状通过校验", () => {
    expect(StoryChapterSchema.safeParse(validChapter).success).toBe(true);
  });

  it("snake_case 旧形状必须失败（守卫后端 artifacts.py 修复）", () => {
    const snake = {
      id: "c1",
      index: 0,
      title: "起点",
      hook: "一句钩子",
      narrative_role: "Hook",
      stop_id: 1,
      relation_to_previous: null,
      evidence_ids: ["f1"],
      walking_minutes: 5,
      cast_refs: ["e1"],
    };
    const res = StoryChapterSchema.safeParse(snake);
    expect(res.success).toBe(false);
  });
});

describe("CuratedStorySchema — evidenceGraph 字段命名契约", () => {
  it("含证据图（camelCase）的 curated_story 通过", () => {
    expect(CuratedStorySchema.safeParse(validStory).success).toBe(true);
  });

  it("缺少 evidenceGraph 必须失败（守卫 embed() 输出 evidenceGraph 而非 evidence_graph）", () => {
    const withoutGraph = { ...validStory } as Record<string, unknown>;
    delete withoutGraph.evidenceGraph;
    const res = CuratedStorySchema.safeParse(withoutGraph);
    expect(res.success).toBe(false);
  });

  it("仅提供 snake_case evidence_graph（缺 camelCase）时必须失败（守卫 embed() 不回退 snake）", () => {
    const withoutCamel = { ...validStory } as Record<string, unknown>;
    delete withoutCamel.evidenceGraph;
    const onlySnake = {
      ...withoutCamel,
      evidence_graph: evidenceGraph,
    } as Record<string, unknown>;
    // evidenceGraph 缺失 → 失败（zod 剥离未知键 evidence_graph，但必填项仍缺）
    const res = CuratedStorySchema.safeParse(onlySnake);
    expect(res.success).toBe(false);
  });
});
