/** 红鸢旁白：按三层 Agentic RAG 分层，加载页对齐取证 / 抽签 / 当代口吻。 */

export const LAYER_TIPS: Record<"L1" | "L2" | "L3" | "idle", string[]> = {
  L1: [
    "红鸢先低头取证：馆藏编号对不上的句子，不会写进这一程。",
    "L1 · 取证——上图建筑、人物、事件先入袋，再谈叙事。",
    "点位若只有轮廓没有出处，红鸢会宁可留白，也不编造阳台传闻当史实。",
    "OSM 画轮廓，上图给证据。红鸢只负责把二者缝进同一条路。",
  ],
  L2: [
    "L2 · 抽签——情绪、声线、叙事角同时落下，决定这一程怎么开口。",
    "红鸢抽到的不是运势，是声音：缓一点、冷一点、还是贴近同行者。",
    "人物进场前，先确认身份层落在册页上——否则宁可不点名。",
    "策展人在装订书页；红鸢在旁边校对：这一句能指回哪条 record_id？",
  ],
  L3: [
    "L3 · 当代口吻——热词只借语气，不作开放时间，不作排队史实。",
    "武康转角机位可以写氛围，不能写成「百年树龄」——红鸢会划掉。",
    "当代读法像一层薄纱：透过它仍要看见馆藏，而不是滤镜本身。",
    "热词过期就换新一周。红鸢不背上周的小红书稿。",
  ],
  idle: [
    "先取证，后叙事——没有出处的句子，不会出现在路线上。",
    "坐标若标「示意」，说明精确落点仍在考证中，别按导航硬闯。",
    "随时可以收尾。这不是打卡游戏，合上书也算读完。",
    "证据够了才开口。不够的话，这一站宁缺毋滥。",
  ],
};

/** @deprecated 兼容旧调用；请优先用 tipsForPhase */
export const LOADING_TIPS: string[] = [
  ...LAYER_TIPS.L1,
  ...LAYER_TIPS.L2,
  ...LAYER_TIPS.L3,
  ...LAYER_TIPS.idle,
];

export function tipsForPhase(phase: string): string[] {
  const p = phase || "";
  if (/取证|检索|馆藏|证据|whitelist|证据链|L1/i.test(p)) return LAYER_TIPS.L1;
  if (/抽签|声线|情绪|叙事|润色|装订|红鸢|L2|voice/i.test(p)) return LAYER_TIPS.L2;
  if (/热词|当代|口吻|社交|L3|hotword/i.test(p)) return LAYER_TIPS.L3;
  return LAYER_TIPS.idle;
}

export function shuffledTips(count = LOADING_TIPS.length): string[] {
  const arr = [...LOADING_TIPS];
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]];
  }
  return arr.slice(0, count);
}
