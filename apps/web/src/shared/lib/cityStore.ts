/**
 * 选中城市的小型全局状态（主页选择 → 头部标识即时反映，无需逐层 props 透传）。
 */
import { create } from "zustand";
import { DEFAULT_CITY } from "./cities";

interface CityState {
  city: string;
  setCity: (c: string) => void;
}

export const useCityStore = create<CityState>((set) => ({
  city: DEFAULT_CITY,
  setCity: (c: string) => set({ city: c || DEFAULT_CITY }),
}));
