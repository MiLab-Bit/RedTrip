const ROLE_LABEL = {
  Hook: "引子",
  Anchor: "锚点",
  Contrast: "对照",
  Reveal: "揭示",
  Afterimage: "余韵",
  Bridge: "过渡",
};

const CHANNEL_LABEL = {
  slc: "上图馆藏",
  landmark: "策展词库",
  osm: "OSM 坐标",
  amap: "地图核录",
  manual: "地名志",
};

const DATASET_LABEL = {
  slc_building: "上图建筑",
  geonames_corpus: "地名志",
  landmark_corpus: "策展词库",
  building_detail: "建筑详情",
  event_list: "事件记载",
};

function buildStoryView(env) {
  const cs = env.curated_story;
  if (cs && cs.chapters && cs.chapters.length > 0) {
    return {
      id: cs.id,
      themeTitle: (cs.theme && cs.theme.title) || env.theme,
      thesis: cs.thesis || env.why_visit || env.curator_note,
      cast: cs.cast || [],
      chapters: cs.chapters.map((c) => ({ ...c })),
      quality: cs.quality || null,
      mode: "curated_story",
    };
  }

  const arc = env.narrative_arc;
  const chapters = env.route.stops.map((s, i) => {
    const node = arc && arc.nodes && arc.nodes.find((n) => n.stop_index === s.order);
    const castRefs = s.layers.filter((l) => l.kind === "person").map((l) => l.label);
    return {
      id: `ch-${s.order}`,
      index: i + 1,
      title: s.name,
      hook: s.meaning,
      narrativeRole: (node && node.role) || "Bridge",
      stopId: s.order,
      relationToPrevious: s.transition_to_next,
      walkingMinutes: s.minutes,
      castRefs,
    };
  });

  const cast = [];
  const seen = new Set();
  for (const s of env.route.stops) {
    for (const l of s.layers) {
      if (l.kind === "person" && !seen.has(l.label)) {
        seen.add(l.label);
        cast.push({
          id: `cast-${l.label}`,
          kind: "person",
          name: l.label,
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
    quality: env.sentence_provenance
      ? {
          coverage_ratio: env.sentence_provenance.coverage_ratio,
        }
      : null,
    mode: "derived",
  };
}

function getStopByOrder(envelope, order) {
  return envelope.route.stops.find((s) => s.order === order) || null;
}

function getStoryBlock(envelope, stopOrder) {
  return (
    envelope.blocks.find((b) => b.type === "story_card" && b.stop_order === stopOrder) || null
  );
}

function findStopClaims(envelope, stopOrder, sourceBlock = "story_card") {
  const sp = envelope.sentence_provenance;
  if (!sp || !sp.per_stop) return [];
  const entry = sp.per_stop.find(
    (p) => p.stop_index === stopOrder && p.source_block === sourceBlock,
  );
  return (entry && entry.sentences) || [];
}

function channelLabel(channel) {
  return CHANNEL_LABEL[channel] || channel || "未标注";
}

function datasetLabel(dataset) {
  return DATASET_LABEL[dataset] || dataset;
}

function shortRecordId(recordId) {
  if (!recordId) return "";
  if (recordId.startsWith("http")) {
    const parts = recordId.replace(/\/$/, "").split("/");
    return parts[parts.length - 1] || recordId.slice(-12);
  }
  if (recordId.length > 28) {
    return recordId.slice(0, 14) + "…" + recordId.slice(-8);
  }
  return recordId;
}

function splitParagraphs(body) {
  if (!body) return [];
  return body.split("\n\n").filter(Boolean);
}

function roleLabel(role) {
  return ROLE_LABEL[role] || role || "章节";
}

module.exports = {
  buildStoryView,
  getStopByOrder,
  getStoryBlock,
  findStopClaims,
  channelLabel,
  datasetLabel,
  shortRecordId,
  splitParagraphs,
  roleLabel,
  ROLE_LABEL,
};
