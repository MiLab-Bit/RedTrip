import type {
  RouteEnvelope,
  EvidenceCluster,
  EvidenceJoin,
  EvidenceFact,
  NarrativeRole,
  StoryQuality,
  StoryEntity,
} from "@redtrip/contracts";

export type StoryViewChapter = {
  id: string;
  index: number;
  title: string;
  hook: string;
  narrativeRole: NarrativeRole;
  stopId: number;
  relationToPrevious: string | null;
  evidenceIds: string[];
  walkingMinutes: number;
  castRefs: string[];
};

export type StoryView = {
  id: string;
  themeTitle: string;
  thesis: string;
  cast: StoryEntity[];
  chapters: StoryViewChapter[];
  evidenceClusters: EvidenceCluster[];
  evidenceJoins: EvidenceJoin[];
  quality: StoryQuality | null;
  /** curated_story 缺席时（快照 / 旧 envelope）由 route + 既有 artifact 合成 */
  mode: "curated_story" | "derived";
};

export function buildStoryView(env: RouteEnvelope): StoryView {
  const cs = env.curated_story;
  if (cs && cs.chapters && cs.chapters.length > 0) {
    return {
      id: cs.id,
      themeTitle: cs.theme?.title || env.theme,
      thesis: cs.thesis || env.why_visit || env.curator_note,
      cast: cs.cast ?? [],
      chapters: cs.chapters.map((c) => ({ ...c })),
      evidenceClusters: cs.evidenceGraph?.clusters ?? [],
      evidenceJoins: cs.evidenceGraph?.joins ?? [],
      quality: cs.quality ?? null,
      mode: "curated_story",
    };
  }

  // 退化路径：curated_story 缺席时，用 route + 既有 artifact 合成一份可读的章节视图
  const arc = env.narrative_arc;
  const chapters: StoryViewChapter[] = env.route.stops.map((s, i) => {
    const node = arc?.nodes?.find((n) => n.stop_index === s.order);
    const castRefs = s.layers
      .filter((l) => l.kind === "person")
      .map((l) => l.label);
    return {
      id: `ch-${s.order}`,
      index: i + 1,
      title: s.name,
      hook: s.meaning,
      narrativeRole: (node?.role ?? "Bridge") as NarrativeRole,
      stopId: s.order,
      relationToPrevious: s.transition_to_next,
      evidenceIds: [],
      walkingMinutes: s.minutes,
      castRefs,
    };
  });

  const cast: StoryEntity[] = [];
  const seen = new Set<string>();
  for (const s of env.route.stops) {
    for (const l of s.layers) {
      if (l.kind === "person" && !seen.has(l.label)) {
        seen.add(l.label);
        cast.push({
          id: `cast-${l.label}`,
          kind: "person",
          name: l.label,
          fact_uri: l.source.record_id,
          note: l.claim,
        });
      }
    }
  }

  return {
    id: env.intent,
    themeTitle: env.theme,
    thesis: env.why_visit || env.curator_note,
    cast,
    chapters,
    evidenceClusters: env.evidence_graph?.clusters ?? [],
    evidenceJoins: env.evidence_graph?.joins ?? [],
    quality: null,
    mode: "derived",
  };
}

export function factByUri(
  view: StoryView,
  uri: string,
): EvidenceFact | undefined {
  for (const cl of view.evidenceClusters) {
    const f = cl.facts.find((x) => x.fact_uri === uri);
    if (f) return f;
  }
  return undefined;
}

export function chapterFacts(
  view: StoryView,
  ch: StoryViewChapter,
): EvidenceFact[] {
  if (ch.evidenceIds.length === 0) return [];
  const out: EvidenceFact[] = [];
  for (const u of ch.evidenceIds) {
    const f = factByUri(view, u);
    if (f) out.push(f);
  }
  return out;
}

export function chapterStop(env: RouteEnvelope, ch: StoryViewChapter) {
  return (
    env.route.stops.find((s) => s.order === ch.stopId) ?? env.route.stops[0]
  );
}
