const {
  buildStoryView,
  getStoryBlock,
  splitParagraphs,
  channelLabel,
} = require("./story");

/** 把流式 chapter_ready 润色卡合并进 envelope.blocks */
function mergeStreamCard(envelope, stopOrder, card) {
  if (!envelope || !card) return envelope;
  const blocks = (envelope.blocks || []).map((b) => {
    if (b.type !== "story_card" || b.stop_order !== stopOrder) return b;
    return {
      ...b,
      title: card.title || b.title,
      body: card.body || b.body,
      age_parallel: card.age_parallel || b.age_parallel,
    };
  });
  return { ...envelope, blocks };
}

/** story_ready 载荷 → 可预览的 envelope */
function envelopeFromStoryReady(payload) {
  if (!payload || !payload.envelope) return null;
  return payload.envelope;
}

module.exports = {
  buildStoryView,
  getStoryBlock,
  splitParagraphs,
  channelLabel,
  mergeStreamCard,
  envelopeFromStoryReady,
};
