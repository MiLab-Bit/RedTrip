import { Component, type ReactNode } from "react";
import type { RouteEnvelope } from "@redtrip/contracts";
import type { FootprintFeature } from "./Footprints";
import { MapSchematic } from "./MapSchematic";
import { MapScene25D } from "./MapScene25D";

type Props = {
  envelope: RouteEnvelope;
  activeOrder?: number;
  onSelectStop: (order: number) => void;
  /** Prefer immersive 2.5D; falls back to SVG schematic on WebGL error. */
  mode?: "auto" | "schematic" | "immersive";
  footprints?: FootprintFeature[];
  osmNote?: string;
};

type ErrState = { failed: boolean };

class WebGLGuard extends Component<
  { fallback: ReactNode; children: ReactNode },
  ErrState
> {
  state: ErrState = { failed: false };

  static getDerivedStateFromError(): ErrState {
    return { failed: true };
  }

  componentDidCatch() {
    // swallow — schematic fallback is enough for demo
  }

  render() {
    if (this.state.failed) return this.props.fallback;
    return this.props.children;
  }
}

export function MapCanvas({
  envelope,
  activeOrder,
  onSelectStop,
  mode = "auto",
  footprints,
  osmNote,
}: Props) {
  const schematic = (
    <MapSchematic
      envelope={envelope}
      activeOrder={activeOrder}
      onSelectStop={onSelectStop}
    />
  );

  if (mode === "schematic") return schematic;

  return (
    <WebGLGuard fallback={schematic}>
      <MapScene25D
        envelope={envelope}
        activeOrder={activeOrder}
        onSelectStop={onSelectStop}
        footprints={footprints}
        osmNote={osmNote}
      />
    </WebGLGuard>
  );
}
