import { useRef } from "react";
import type { FlipDirection } from "./PageFlip";

export type TripPhase =
  | "brief"
  | "loading"
  | "map"
  | "walking"
  | "done"
  | "degraded";

const phaseRank: Record<TripPhase, number> = {
  brief: 0,
  loading: 1,
  map: 2,
  walking: 3,
  done: 4,
  degraded: 2,
};

function inferPhaseDirection(from: TripPhase, to: TripPhase): FlipDirection {
  if (to === "brief") return "close";
  if (from === "brief" && to === "loading") return "open";
  if (to === "done") return "close";
  if (to === "degraded") return "back";
  if (from === "walking" && to === "map") return "back";
  if (phaseRank[to] < phaseRank[from]) return "back";
  return "forward";
}

/** Infer flip direction from trip phase + stop order (sync, same frame as key). */
export function useFlipController(phase: TripPhase, stopOrder: number) {
  const prevPhase = useRef(phase);
  const prevStop = useRef(stopOrder);
  const directionRef = useRef<FlipDirection>("open");

  if (phase !== prevPhase.current) {
    directionRef.current = inferPhaseDirection(prevPhase.current, phase);
    prevPhase.current = phase;
    prevStop.current = stopOrder;
  } else if (phase === "walking" && stopOrder !== prevStop.current) {
    directionRef.current =
      stopOrder > prevStop.current ? "forward" : "back";
    prevStop.current = stopOrder;
  }

  const pageKey = phase === "walking" ? `walking-${stopOrder}` : phase;

  return { pageKey, direction: directionRef.current };
}
