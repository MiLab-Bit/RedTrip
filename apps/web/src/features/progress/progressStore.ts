import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";

/** 一条「线路」的阅读进度快照（仅摘要，不存完整 envelope，避免撑爆 localStorage）。 */
export interface RouteProgress {
  theme: string;
  thesis?: string;
  chapterTitles: string[];
  currentChapter: number;
  totalChapters: number;
  finished: boolean;
  updatedAt: number;
}

interface ProgressState {
  /** key = userId（登录）或 "anon"（游客）。不同账号进度完全隔离。 */
  byUser: Record<string, RouteProgress>;
  record: (userId: string | null, p: RouteProgress) => void;
  getFor: (userId: string | null) => RouteProgress | undefined;
}

const keyOf = (userId: string | null) => userId ?? "anon";

export const useProgressStore = create<ProgressState>()(
  persist(
    (set, get) => ({
      byUser: {},
      record: (userId, p) =>
        set((s) => ({ byUser: { ...s.byUser, [keyOf(userId)]: p } })),
      getFor: (userId) => get().byUser[keyOf(userId)],
    }),
    {
      name: "redtrip:progress",
      storage: createJSONStorage(() => localStorage),
    },
  ),
);
