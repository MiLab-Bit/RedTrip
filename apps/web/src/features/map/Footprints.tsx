import { useLayoutEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { bakeFootprintBatch, type ProjectFn } from "./osm/pipeline";
import type { FootprintFeature } from "./osm/types";

export type { FootprintFeature };
export type BakeStats = {
  count: number;
  discarded: number;
  radius: number;
  center: [number, number, number];
};

/**
 * Batched OSM city masses.
 * Bake synchronously in useLayoutEffect (StrictMode-safe; no rAF cancel).
 */
export function OsmFootprints({
  features,
  project,
  anchors = [],
  maxDist = 220,
  onBaked,
}: {
  features: FootprintFeature[];
  project: ProjectFn;
  anchors?: Array<{ x: number; z: number }>;
  maxDist?: number;
  onBaked?: (stats: BakeStats | null) => void;
}) {
  const anchorsKey = useMemo(
    () => anchors.map((a) => `${a.x.toFixed(1)},${a.z.toFixed(1)}`).join("|"),
    [anchors],
  );
  const anchorsRef = useRef(anchors);
  anchorsRef.current = anchors;
  const onBakedRef = useRef(onBaked);
  onBakedRef.current = onBaked;

  const [geometry, setGeometry] = useState<THREE.BufferGeometry | null>(null);
  const geoRef = useRef<THREE.BufferGeometry | null>(null);

  useLayoutEffect(() => {
    if (geoRef.current) {
      geoRef.current.dispose();
      geoRef.current = null;
    }

    if (!features.length) {
      setGeometry(null);
      onBakedRef.current?.(null);
      return;
    }

    const result = bakeFootprintBatch(features, project, {
      anchors: anchorsRef.current,
      maxDist,
      maxBuildings: 80,
      simplifyM: 0.55,
    });

    if (!result) {
      setGeometry(null);
      onBakedRef.current?.(null);
      return;
    }

    geoRef.current = result.geometry;
    setGeometry(result.geometry);
    onBakedRef.current?.({
      count: result.count,
      discarded: result.discarded,
      radius: result.radius,
      center: result.center,
    });

    return () => {
      if (geoRef.current) {
        geoRef.current.dispose();
        geoRef.current = null;
      }
      setGeometry(null);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- anchors via anchorsKey
  }, [features, project, anchorsKey, maxDist]);

  if (!geometry) return null;

  return (
    <mesh
      geometry={geometry}
      receiveShadow
      castShadow={false}
      frustumCulled={false}
    >
      <meshStandardMaterial
        vertexColors
        roughness={0.95}
        metalness={0}
        flatShading
        side={THREE.DoubleSide}
      />
    </mesh>
  );
}
