import { z } from "zod";

export const GeoPointSchema = z.object({
  lat: z.number(),
  lng: z.number(),
  coord_source: z.enum(["manual", "upstream", "amap", "osm", "none"]),
  precision: z.enum(["exact", "approximate", "schematic"]),
});
export type GeoPoint = z.infer<typeof GeoPointSchema>;

export const SourceRefSchema = z.object({
  dataset: z.string().min(1),
  record_id: z.string().min(1),
  excerpt: z.string().optional(),
});
export type SourceRef = z.infer<typeof SourceRefSchema>;

export const IdentityLayerSchema = z.object({
  kind: z.enum(["building", "event", "era", "poem", "person", "geoname", "literary"]),
  label: z.string(),
  claim: z.string(),
  source: SourceRefSchema,
});
export type IdentityLayer = z.infer<typeof IdentityLayerSchema>;

export const RouteStopSchema = z.object({
  order: z.number().int().positive(),
  whitelist_id: z.string(),
  buri: z.string().nullable(),
  name: z.string(),
  minutes: z.number().positive(),
  meaning: z.string(),
  transition_to_next: z.string().nullable(),
  layers: z.array(IdentityLayerSchema),
  geo: GeoPointSchema,
  pitfalls: z.object({
    open_hours: z.string(),
    enterable: z.string(),
    need_reservation: z.string(),
  }),
  /** L1 通道诚实标注：馆藏 / 地标词库 / OSM / 人工 */
  evidence_channel: z
    .enum(["slc", "landmark", "osm", "manual", "amap"])
    .nullish(),
  /** 规划四段节奏：序章 / 聚焦 / 过渡 / 跋 */
  act: z.enum(["prologue", "focus", "transit", "epilogue"]).nullish(),
});
export type RouteStop = z.infer<typeof RouteStopSchema>;

export const StoryCardBlockSchema = z.object({
  type: z.literal("story_card"),
  stop_order: z.number().int().positive(),
  title: z.string(),
  body: z.string(),
  age_parallel: z.string().optional(),
  sources: z.array(SourceRefSchema),
});

export const EssayBlockSchema = z.object({
  type: z.literal("essay"),
  stop_order: z.number().int().positive(),
  title: z.string(),
  body: z.string(),
  /** LLM 溯源附注；前端可不消费 */
  provenance: z.unknown().optional(),
});

export const SceneBlockSchema = z.object({
  type: z.literal("scene"),
  stop_order: z.number().int().positive(),
  place: z.string(),
  era_desc: z.string(),
  figures: z.string(),
  city_thread: z.string(),
  today: z.string(),
  visual_note: z.string(),
});

export const CardBlockSchema = z.object({
  type: z.literal("card"),
  title: z.string(),
  lead: z.string(),
  keywords: z.array(z.string()),
  body: z.string(),
  coda: z.string(),
});

export const BlockSchema = z.discriminatedUnion("type", [
  StoryCardBlockSchema,
  EssayBlockSchema,
  SceneBlockSchema,
  CardBlockSchema,
]);
export type Block = z.infer<typeof BlockSchema>;
export type EssayBlock = z.infer<typeof EssayBlockSchema>;


// ===========================================================================
// G2 / G4 稳定契约：内容推理层四个一等公民中间产物
// 字段命名全仓统一 snake_case，与 Python dict 输出直接对应。
// ===========================================================================

export const LayerKindSchema = z.enum([
  "building",
  "event",
  "era",
  "poem",
  "person",
  "geoname",
  "literary",
]);
export type LayerKind = z.infer<typeof LayerKindSchema>;

export const NarrativeRoleSchema = z.enum([
  "Hook",
  "Anchor",
  "Contrast",
  "Reveal",
  "Afterimage",
  "Bridge",
]);
export type NarrativeRole = z.infer<typeof NarrativeRoleSchema>;

// G2-1 Theme（研究命题 / 开放问题入口）
export const ResearchAxisSchema = z.object({
  axis: z.string(),
  hypothesis: z.string(),
  evidence_cluster_ids: z.array(z.string()),
});
export type ResearchAxis = z.infer<typeof ResearchAxisSchema>;

export const ThemeSchema = z.object({
  id: z.string(),
  title: z.string(),
  open_question: z.string(),
  research_axes: z.array(ResearchAxisSchema),
  why_visit: z.string(),
  estimated_duration_min: z.number().int(),
  scope_note: z.string(),
});
export type Theme = z.infer<typeof ThemeSchema>;

// G2-2 EvidenceGraph（证据图：聚类 + buri 跨库 join）
export const EvidenceFactSchema = z.object({
  fact_uri: z.string(),
  label: z.string(),
  assertion: z.string(),
  layer: LayerKindSchema,
  source_dataset: z.string(),
  confidence: z.number(),
});
export type EvidenceFact = z.infer<typeof EvidenceFactSchema>;

export const EvidenceClusterSchema = z.object({
  id: z.string(),
  dimension: z.string(),
  label: z.string(),
  facts: z.array(EvidenceFactSchema),
});
export type EvidenceCluster = z.infer<typeof EvidenceClusterSchema>;

export const EvidenceJoinSchema = z.object({
  from_uri: z.string(),
  to_uri: z.string(),
  relation: z.string(),
});
export type EvidenceJoin = z.infer<typeof EvidenceJoinSchema>;

export const EvidenceGraphSchema = z.object({
  theme_id: z.string(),
  clusters: z.array(EvidenceClusterSchema),
  joins: z.array(EvidenceJoinSchema),
  coverage: z.record(z.any()),
});
export type EvidenceGraph = z.infer<typeof EvidenceGraphSchema>;

// G2-3 NarrativeArc（叙事弧：节点叙事角色 + 张力曲线）
export const NarrativeNodeSchema = z.object({
  stop_index: z.number().int(),
  role: NarrativeRoleSchema,
  beat: z.string(),
  facts_referenced: z.array(z.string()),
});
export type NarrativeNode = z.infer<typeof NarrativeNodeSchema>;

export const NarrativeArcSchema = z.object({
  theme_id: z.string(),
  nodes: z.array(NarrativeNodeSchema),
  tension_curve: z.array(z.number()),
});
export type NarrativeArc = z.infer<typeof NarrativeArcSchema>;

// 故事优先：内容结构（前端 StoryReader / NarrativeArc 直接消费的 CuratedStory）
export const StoryEntityKindSchema = z.enum(["person", "building", "event"]);
export type StoryEntityKind = z.infer<typeof StoryEntityKindSchema>;

export const StoryEntitySchema = z.object({
  id: z.string(),
  kind: StoryEntityKindSchema,
  name: z.string(),
  fact_uri: z.string().nullable(),
  note: z.string().nullable(),
});
export type StoryEntity = z.infer<typeof StoryEntitySchema>;

export const StoryChapterSchema = z.object({
  id: z.string(),
  index: z.number().int(),
  title: z.string(),
  hook: z.string(),
  narrativeRole: NarrativeRoleSchema,
  stopId: z.number().int(),
  relationToPrevious: z.string().nullable(),
  evidenceIds: z.array(z.string()),
  walkingMinutes: z.number(),
  castRefs: z.array(z.string()),
});
export type StoryChapter = z.infer<typeof StoryChapterSchema>;

export const StoryQualitySchema = z.object({
  evidence_layers: z.number().int(),
  coverage_ratio: z.number(),
  aligned_ratio: z.number(),
});
export type StoryQuality = z.infer<typeof StoryQualitySchema>;

// G4 ProvenanceReport（细粒度溯源：断言 ↔ 事实）
export const AssertionClaimSchema = z.object({
  text: z.string(),
  fact_uri: z.string().nullable(),
  aligned: z.boolean(),
  layer: LayerKindSchema.nullable(),
});
export type AssertionClaim = z.infer<typeof AssertionClaimSchema>;

export const StopProvenanceSchema = z.object({
  stop_index: z.number().int(),
  assertions: z.array(AssertionClaimSchema),
});
export type StopProvenance = z.infer<typeof StopProvenanceSchema>;

export const ProvenanceReportSchema = z.object({
  total_assertions: z.number().int(),
  aligned_assertions: z.number().int(),
  coverage_ratio: z.number(),
  per_stop: z.array(StopProvenanceSchema),
});
export type ProvenanceReport = z.infer<typeof ProvenanceReportSchema>;

// G4-sentence：句子级细粒度溯源（对渲染后叙事逐句标注 factual/connective 并映射 fact_uri）
export const SentenceClaimSchema = z.object({
  index: z.number().int(),
  text: z.string(),
  kind: z.enum(["factual", "connective"]),
  fact_uris: z.array(z.string()),
  fact_labels: z.array(z.string()),
  aligned: z.boolean(),
});
export type SentenceClaim = z.infer<typeof SentenceClaimSchema>;

export const StopSentenceProvenanceSchema = z.object({
  stop_index: z.number().int(),
  source_block: z.string(),
  sentences: z.array(SentenceClaimSchema),
});
export type StopSentenceProvenance = z.infer<typeof StopSentenceProvenanceSchema>;

export const SentenceProvenanceReportSchema = z.object({
  total_sentences: z.number().int(),
  factual_sentences: z.number().int(),
  aligned_factual: z.number().int(),
  coverage_ratio: z.number(),
  per_stop: z.array(StopSentenceProvenanceSchema),
});
export type SentenceProvenanceReport = z.infer<
  typeof SentenceProvenanceReportSchema
>;

// Bundle
export const CurationArtifactsSchema = z.object({
  artifacts_version: z.string(),
  theme: ThemeSchema,
  evidence_graph: EvidenceGraphSchema,
  narrative_arc: NarrativeArcSchema,
  provenance: ProvenanceReportSchema,
  sentence_provenance: SentenceProvenanceReportSchema.nullish(),
  // 故事优先：CuratedStory 内容结构（前端 StoryReader / NarrativeArc 直接消费）
  thesis: z.string(),
  cast: z.array(StoryEntitySchema),
  chapters: z.array(StoryChapterSchema),
});
export type CurationArtifacts = z.infer<typeof CurationArtifactsSchema>;


export const WalkRouteSchema = z.object({
  duration_min: z.number().positive(),
  walk_meters_est: z.number().nonnegative(),
  stops: z.array(RouteStopSchema).min(3).max(10),
});
export type WalkRoute = z.infer<typeof WalkRouteSchema>;

// 故事优先：CuratedStory 内容结构（前端 StoryReader / NarrativeArc 直接消费）
export const CuratedStorySchema = z.object({
  id: z.string(),
  theme: ThemeSchema,
  thesis: z.string(),
  cast: z.array(StoryEntitySchema),
  chapters: z.array(StoryChapterSchema),
  evidenceGraph: EvidenceGraphSchema,
  // route 为可选：唯一数据源是 envelope.route，curated_story 不再重复携带整条路线
  // （重复序列化会让响应体积多出约 49%）。旧 envelope 内若带 route 仍可通过校验。
  route: WalkRouteSchema.nullish(),
  quality: StoryQualitySchema.nullish(),
});
export type CuratedStory = z.infer<typeof CuratedStorySchema>;

export const RouteEnvelopeSchema = z.object({
  envelope_version: z.literal("1.0"),
  intent: z.string(),
  theme: z.string(),
  logic_line: z.string(),
  aesthetic: z.string(),
  scenario: z.string(),
  why_visit: z.string(),
  curator_note: z.string(),
  assumptions: z.array(z.string()),
  companions: z.enum(["solo", "duo", "small_group"]),
  sources: z.array(z.string()),
  route: WalkRouteSchema,
  blocks: z.array(BlockSchema),
  // G2/G4: 可选注入的四个一等公民中间产物（旧 envelope / 快照 fixture 不含这些字段）
  theme_artifact: ThemeSchema.nullish(),
  evidence_graph: EvidenceGraphSchema.nullish(),
  narrative_arc: NarrativeArcSchema.nullish(),
  provenance: ProvenanceReportSchema.nullish(),
  sentence_provenance: SentenceProvenanceReportSchema.nullish(),
  curation_artifacts: CurationArtifactsSchema.nullish(),
  // 反方策展人评审（非阻断）；前端「策展留白」与书页附录消费
  curator_review: z
    .object({
      concerns: z
        .array(
          z.object({
            claim: z.string().nullish(),
            node: z.string().nullish(),
            mechanism: z.string().nullish(),
            fix: z.string().nullish(),
          }),
        )
        .nullish(),
      missed_voices: z.array(z.string()).nullish(),
      skipped_harder_node: z.string().nullish(),
      alternative_thesis: z.string().nullish(),
      reverse_route_note: z.string().nullish(),
      warnings: z.array(z.string()).nullish(),
    })
    .passthrough()
    .nullish(),
  // 故事优先：CuratedStory 内容结构（前端 StoryReader / NarrativeArc 直接消费）
  thesis: z.string().nullish(),
  cast: z.array(StoryEntitySchema).nullish(),
  chapters: z.array(StoryChapterSchema).nullish(),
  curated_story: CuratedStorySchema.nullish(),
});
export type RouteEnvelope = z.infer<typeof RouteEnvelopeSchema>;
export type CuratorReview = NonNullable<RouteEnvelope["curator_review"]>;

export const IntentSlotsSchema = z.object({
  audience: z.string().nullable(),
  scene: z.string().nullable(),
  duration_min: z.number().nullable(),
  tone: z.string().nullable(),
  delivery: z.string().nullable(),
  companions: z.string().nullable(),
  // daypart: day 白天 / night 夜晚（排除 21 点前关门的，匹配夜生活）/ full 全天 / suburb 郊区（自然景点）
  daypart: z.enum(["day", "night", "full", "suburb"]).nullable(),
  // 策展城市 key（见后端 redtrip_curator.cities.CITY_REGISTRY）。缺省 shanghai。
  city: z.string().nullable(),
});
export type IntentSlots = z.infer<typeof IntentSlotsSchema>;

export const CurateRequestSchema = z.object({
  message: z.string().optional(),
  slots: IntentSlotsSchema.partial().optional(),
  retry_count: z.number().int().nonnegative().default(0),
});
export type CurateRequest = z.infer<typeof CurateRequestSchema>;

export const HongyuanSlotSchema = z.object({
  category: z.string(),
  id: z.string(),
  label: z.string(),
  hint: z.string(),
});
export type HongyuanSlot = z.infer<typeof HongyuanSlotSchema>;

export const HongyuanHotwordSchema = z.object({
  id: z.string(),
  term: z.string(),
  places: z.array(z.string()).nullish(),
  hint: z.string().nullish(),
  heat: z.number().nullish(),
  week: z.string().nullish(),
  score: z.number().nullish(),
});
export type HongyuanHotword = z.infer<typeof HongyuanHotwordSchema>;

export const HongyuanMetaSchema = z.object({
  agent: z.string(),
  seed: z.number().nullish(),
  summary: z.string().nullish(),
  emotion: HongyuanSlotSchema.nullish(),
  voice_style: HongyuanSlotSchema.nullish(),
  narrative: HongyuanSlotSchema.nullish(),
  knowledge_angle: HongyuanSlotSchema.nullish(),
  pacing: HongyuanSlotSchema.nullish(),
  lexicon_size: z.record(z.number()).nullish(),
  layer3_week: z.string().nullish(),
  layer3_summary: z.string().nullish(),
  layer3: z.array(HongyuanHotwordSchema).nullish(),
  rag_layers: z.array(z.string()).nullish(),
});
export type HongyuanMeta = z.infer<typeof HongyuanMetaSchema>;

export const CurateResponseSchema = z.object({
  status: z.enum(["ok", "degraded"]),
  // FastAPI/Pydantic often serializes unset optionals as null — accept nullish.
  phase: z.enum(["skeleton", "full"]).nullish(),
  envelope: RouteEnvelopeSchema.nullish(),
  // G2: 四个一等公民中间产物（Theme / EvidenceGraph / NarrativeArc / Provenance）
  artifacts: CurationArtifactsSchema.nullish(),
  reasons: z.array(z.string()).nullish(),
  meta: z
    .object({
      latency_ms: z.number().nullish(),
      assumptions: z.array(z.string()).nullish(),
      mode: z.enum(["snapshot", "indexed", "mcp"]).nullish(),
      evidence_count: z.number().nullish(),
      narrative: z.enum(["template", "llm_polish"]).nullish(),
      hongyuan: HongyuanMetaSchema.nullish(),
      gate: z
        .object({
          passed: z.boolean(),
          warnings: z.array(z.string()).nullish(),
        })
        .nullish(),
    })
    .nullish(),
});
export type CurateResponse = z.infer<typeof CurateResponseSchema>;
