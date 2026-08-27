import { assign, setup } from "xstate";
import type {
  HongyuanMeta,
  RouteEnvelope,
  SourceRef,
} from "@redtrip/contracts";
import type { FootprintFeature } from "../map/Footprints";

/** 章节所在站点的 order（用于地图子视图高亮 / 退化回退）。 */
function chapterStopId(env: RouteEnvelope | null, index: number): number {
  if (!env) return index;
  const cs = env.curated_story;
  if (cs?.chapters?.length) {
    const ch = cs.chapters[Math.min(index, cs.chapters.length) - 1];
    if (ch) return ch.stopId;
  }
  return index;
}

/** 站点 order → 对应章节 index（地图子视图点节点回到阅读器）。 */
function chapterIndexForStop(env: RouteEnvelope | null, order: number): number {
  if (!env) return 1;
  const cs = env.curated_story;
  if (cs?.chapters?.length) {
    const ch = cs.chapters.find((c) => c.stopId === order);
    if (ch) return ch.index;
  }
  return order;
}

export type TripContext = {
  envelope: RouteEnvelope | null;
  currentStop: number;
  currentChapter: number;
  mapReturn: "storyIntro" | "storyReader";
  source: SourceRef | null;
  error: string | null;
  assumptions: string[];
  hongyuan: HongyuanMeta | null;
  footprints: FootprintFeature[];
  osmNote: string;
  /** brief→loading 时锁定：demo 冻结包 / curate 真实策展 */
  loadMode: "demo-wukang" | "demo-yida" | "curate" | null;
};

export type TripEvent =
  | { type: "SUBMIT" }
  | { type: "SUBMIT_DEMO_WUKANG" }
  | { type: "SUBMIT_DEMO_YIDA" }
  | {
      type: "LOADED";
      envelope: RouteEnvelope;
      assumptions: string[];
      hongyuan: HongyuanMeta | null;
      footprints: FootprintFeature[];
      osmNote: string;
    }
  | { type: "FAIL"; error: string }
  | { type: "BEGIN_STORY" }
  | { type: "OPEN_CHAPTER"; index: number }
  | { type: "NEXT_CHAPTER" }
  | { type: "PREV_CHAPTER" }
  | { type: "OPEN_STOP"; order: number }
  | { type: "OPEN_SOURCE"; source: SourceRef }
  | { type: "CLOSE_SOURCE" }
  | { type: "SHOW_MAP" }
  | { type: "BACK_FROM_MAP" }
  | { type: "BACK_INTRO" }
  | { type: "FINISH" }
  | { type: "RESTART" };

const clearedExtras = {
  footprints: [] as FootprintFeature[],
  osmNote: "",
};

const resetContext = {
  envelope: null,
  currentStop: 1,
  currentChapter: 1,
  mapReturn: "storyIntro" as const,
  source: null,
  error: null,
  assumptions: [],
  hongyuan: null,
  loadMode: null as "demo-wukang" | "demo-yida" | "curate" | null,
  ...clearedExtras,
};

export const tripMachine = setup({
  types: {
    context: {} as TripContext,
    events: {} as TripEvent,
  },
  guards: {
    returnToIntro: ({ context }) => context.mapReturn === "storyIntro",
  },
}).createMachine({
  id: "trip",
  initial: "brief",
  context: {
    envelope: null,
    currentStop: 1,
    currentChapter: 1,
    mapReturn: "storyIntro",
    source: null,
    error: null,
    assumptions: [],
    hongyuan: null,
    footprints: [],
    osmNote: "",
    loadMode: null,
  },
  states: {
    brief: {
      on: {
        SUBMIT: {
          target: "loading",
          actions: assign({ loadMode: "curate" }),
        },
        SUBMIT_DEMO_WUKANG: {
          target: "loading",
          actions: assign({ loadMode: "demo-wukang" }),
        },
        SUBMIT_DEMO_YIDA: {
          target: "loading",
          actions: assign({ loadMode: "demo-yida" }),
        },
      },
    },
    loading: {
      on: {
        LOADED: {
          // 故事优先：取证完成后先进入「序章」，而非直接地图
          target: "storyIntro",
          actions: assign(({ event }) => ({
            envelope: event.envelope,
            assumptions: event.assumptions,
            hongyuan: event.hongyuan,
            footprints: event.footprints,
            osmNote: event.osmNote,
            currentStop: chapterStopId(event.envelope, 1),
            currentChapter: 1,
            source: null,
            error: null,
            mapReturn: "storyIntro",
            loadMode: null,
          })),
        },
        FAIL: {
          target: "degraded",
          actions: assign(({ event }) => ({
            error: event.error,
            loadMode: null,
          })),
        },
      },
    },
    // 序章：thesis / 人物 / 章节脉络 / 章节列表 —— 故事作为入口
    storyIntro: {
      on: {
        BEGIN_STORY: {
          target: "storyReader",
          actions: assign(({ context }) => ({
            currentChapter: 1,
            currentStop: chapterStopId(context.envelope, 1),
          })),
        },
        SHOW_MAP: {
          target: "map",
          actions: assign({ mapReturn: "storyIntro" }),
        },
        RESTART: {
          target: "brief",
          actions: assign(resetContext),
        },
      },
    },
    // 阅读器：章节轨 + 叙事卡 + 证据抽屉（地图降级为子视图，经 SHOW_MAP 进入）
    storyReader: {
      on: {
        OPEN_CHAPTER: {
          actions: assign(({ context, event }) => {
            const max =
              context.envelope?.curated_story?.chapters?.length ??
              context.envelope?.route.stops.length ??
              1;
            const idx = Math.min(Math.max(1, event.index), max);
            return {
              currentChapter: idx,
              currentStop: chapterStopId(context.envelope, idx),
              source: null,
            };
          }),
        },
        NEXT_CHAPTER: {
          actions: assign(({ context }) => {
            const max =
              context.envelope?.curated_story?.chapters?.length ??
              context.envelope?.route.stops.length ??
              1;
            const idx = Math.min(max, context.currentChapter + 1);
            return {
              currentChapter: idx,
              currentStop: chapterStopId(context.envelope, idx),
            };
          }),
        },
        PREV_CHAPTER: {
          actions: assign(({ context }) => {
            const idx = Math.max(1, context.currentChapter - 1);
            return {
              currentChapter: idx,
              currentStop: chapterStopId(context.envelope, idx),
            };
          }),
        },
        OPEN_SOURCE: {
          actions: assign(({ event }) => ({ source: event.source })),
        },
        CLOSE_SOURCE: {
          actions: assign({ source: null }),
        },
        SHOW_MAP: {
          target: "map",
          actions: assign({ mapReturn: "storyReader" }),
        },
        BACK_INTRO: "storyIntro",
        FINISH: "done",
        RESTART: {
          target: "brief",
          actions: assign(resetContext),
        },
      },
    },
    // 全图：作为子视图，从序章或阅读器进入，BACK 返回来处
    map: {
      on: {
        OPEN_STOP: {
          target: "storyReader",
          actions: assign(({ context, event }) => ({
            currentStop: event.order,
            currentChapter: chapterIndexForStop(context.envelope, event.order),
          })),
        },
        BACK_FROM_MAP: [
          { target: "storyIntro", guard: "returnToIntro" },
          { target: "storyReader" },
        ],
        FINISH: "done",
        RESTART: {
          target: "brief",
          actions: assign(resetContext),
        },
      },
    },
    done: {
      on: {
        RESTART: {
          target: "brief",
          actions: assign(resetContext),
        },
      },
    },
    degraded: {
      on: {
        RESTART: {
          target: "brief",
          actions: assign(resetContext),
        },
      },
    },
  },
});
