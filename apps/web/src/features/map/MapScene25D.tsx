import { Canvas, useThree } from "@react-three/fiber";
import { Billboard, ContactShadows, Html, OrbitControls } from "@react-three/drei";
import {
  Suspense,
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useState,
} from "react";
import type { RouteEnvelope } from "@redtrip/contracts";
import { lerp, projectStops } from "./geo";
import {
  LaneHouse,
  PALETTE,
  PlaneTree,
  RouteRibbon,
  ShikumenHero,
  VillaHero,
} from "./buildings/HaipaiArchitecture";
import {
  OsmFootprints,
  type BakeStats,
  type FootprintFeature,
} from "./Footprints";
import { fetchFootprints } from "../../shared/lib/footprints";

type Props = {
  envelope: RouteEnvelope;
  activeOrder?: number;
  onSelectStop: (order: number) => void;
};

function hash01(n: number) {
  const x = Math.sin(n * 12.9898) * 43758.5453;
  return x - Math.floor(x);
}

type StopSite = {
  order: number;
  name: string;
  x: number;
  z: number;
  heroKind: "shikumen" | "villa";
  act?: string | null;
};

const ACT_SHORT: Record<string, string> = {
  prologue: "序",
  focus: "聚",
  transit: "渡",
  epilogue: "跋",
};

function usePerfProfile() {
  return useMemo(() => {
    const mobile =
      typeof window !== "undefined" &&
      window.matchMedia("(max-width: 860px)").matches;
    const saveData =
      typeof navigator !== "undefined" &&
      "connection" in navigator &&
      Boolean(
        (navigator as Navigator & { connection?: { saveData?: boolean } })
          .connection?.saveData,
      );
    const softShadow = !mobile && !saveData;
    return {
      mobile,
      dpr: (mobile ? [1, 1.25] : [1, 1.5]) as [number, number],
      softShadow,
      shadowMap: mobile ? 512 : 1024,
    };
  }, []);
}

function CameraRig({
  camDist,
  target,
}: {
  camDist: number;
  target: [number, number, number];
}) {
  const { camera } = useThree();
  useLayoutEffect(() => {
    camera.position.set(
      target[0] + camDist * 0.62,
      camDist * 0.48,
      target[2] + camDist * 0.62,
    );
    camera.lookAt(target[0], target[1], target[2]);
    camera.updateProjectionMatrix();
  }, [camera, camDist, target[0], target[1], target[2]]);
  return null;
}

function PaperGround({ span }: { span: number }) {
  const size = Math.max(140, span * 1.7);
  return (
    <group>
      <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow position={[0, -0.02, 0]}>
        <planeGeometry args={[size, size]} />
        <meshStandardMaterial
          color={PALETTE.xuan}
          roughness={1}
          metalness={0}
          flatShading
        />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.01, 0]} receiveShadow>
        <circleGeometry args={[size * 0.48, 48]} />
        <meshStandardMaterial
          color={PALETTE.rice}
          roughness={1}
          metalness={0}
          flatShading
        />
      </mesh>
    </group>
  );
}

function StopMarker({
  site,
  active,
  onSelect,
}: {
  site: StopSite;
  active: boolean;
  onSelect: () => void;
}) {
  const roofY = site.heroKind === "villa" ? 13.5 : 14.2;
  return (
    <group position={[site.x, 0, site.z]}>
      {site.heroKind === "villa" ? (
        <VillaHero active={active} onSelect={onSelect} />
      ) : (
        <ShikumenHero active={active} onSelect={onSelect} stories={3} />
      )}
      <Billboard position={[0, roofY, 0]}>
        <Html center distanceFactor={56} style={{ pointerEvents: "none" }}>
          <div className={`map25-card${active ? " is-active" : ""}`}>
            <span className="map25-num">{site.order}</span>
            <span className="map25-name">{site.name}</span>
            {site.act ? (
              <span className={`map25-act is-${site.act}`}>
                {ACT_SHORT[site.act] ?? site.act}
              </span>
            ) : null}
          </div>
        </Html>
      </Billboard>
    </group>
  );
}

function Scene({
  envelope,
  activeOrder,
  onSelectStop,
  footprints,
  softShadow,
  shadowMap,
  onBaked,
  bakeRadius = 80,
  bakeCenter = [0, 3, 0],
}: Props & {
  footprints: FootprintFeature[];
  softShadow: boolean;
  shadowMap: number;
  onBaked?: (stats: BakeStats | null) => void;
  bakeRadius?: number;
  bakeCenter?: [number, number, number];
}) {
  const projector = useMemo(() => projectStops(envelope), [envelope]);
  const { points, span, project } = projector;

  const stops: StopSite[] = useMemo(
    () =>
      points.map(({ stop, x, z }, i) => ({
        order: stop.order,
        name: stop.name,
        x,
        z,
        heroKind: i % 2 === 0 ? "shikumen" : "villa",
        act: stop.act ?? null,
      })),
    [points],
  );

  const path = useMemo(
    () => points.map((p) => [p.x, 0.28, p.z] as [number, number, number]),
    [points],
  );

  const anchors = useMemo(
    () => points.map((p) => ({ x: p.x, z: p.z })),
    [points],
  );

  const trees = useMemo(() => {
    const out: Array<{ id: string; x: number; z: number; scale: number }> = [];
    for (let i = 0; i < points.length - 1; i++) {
      const a = points[i];
      const b = points[i + 1];
      const mx = lerp(a.x, b.x, 0.5);
      const mz = lerp(a.z, b.z, 0.5);
      const nx = -(b.z - a.z);
      const nz = b.x - a.x;
      const len = Math.hypot(nx, nz) || 1;
      out.push({
        id: `t-${i}a`,
        x: mx + (nx / len) * 5.5,
        z: mz + (nz / len) * 5.5,
        scale: 0.85 + hash01(i) * 0.3,
      });
    }
    return out;
  }, [points]);

  const lanes = useMemo(() => {
    if (footprints.length >= 12) return [];
    const out: Array<{
      id: string;
      x: number;
      z: number;
      rot: number;
      w: number;
      d: number;
      h: number;
      seed: number;
    }> = [];
    for (let i = 0; i < points.length - 1; i++) {
      const a = points[i];
      const b = points[i + 1];
      const bx = lerp(a.x, b.x, 0.5);
      const bz = lerp(a.z, b.z, 0.5);
      const nx = -(b.z - a.z);
      const nz = b.x - a.x;
      const len = Math.hypot(nx, nz) || 1;
      out.push({
        id: `lane-${i}`,
        x: bx + (nx / len) * 12,
        z: bz + (nz / len) * 12,
        rot: Math.atan2(nz, nx),
        w: 3.8,
        d: 3.4,
        h: 5.2 + hash01(i) * 2,
        seed: i,
      });
    }
    return out;
  }, [points, footprints.length]);

  const projectLatLng = useMemo(
    () => (lat: number, lng: number) => project(lat, lng),
    [project],
  );
  const corridorDist = Math.max(200, span * 0.85);
  const viewSpan = Math.max(span, bakeRadius * 1.35, 90);
  const camDist = Math.max(72, viewSpan * 0.78);
  const fogFar = camDist * 2.8;
  const fogNear = camDist * 0.85;
  const activeSite = stops.find((s) => s.order === activeOrder);
  const target: [number, number, number] = activeSite
    ? [activeSite.x, 4.2, activeSite.z]
    : [bakeCenter[0] * 0.35, 4, bakeCenter[2] * 0.35];

  return (
    <>
      <color attach="background" args={[PALETTE.xuan]} />
      <fog attach="fog" args={[PALETTE.xuan, fogNear, fogFar]} />
      <CameraRig camDist={camDist * (activeSite ? 0.72 : 1)} target={target} />

      <ambientLight intensity={0.62} color={PALETTE.rice} />
      <hemisphereLight args={[PALETTE.xuan, PALETTE.ochre, 0.7]} />
      <directionalLight
        castShadow
        position={[48, 42, 22]}
        intensity={1.05}
        color="#FFE8C8"
        shadow-mapSize={[shadowMap, shadowMap]}
        shadow-bias={-0.00025}
        shadow-normalBias={0.04}
        shadow-camera-far={220}
        shadow-camera-left={-90}
        shadow-camera-right={90}
        shadow-camera-top={90}
        shadow-camera-bottom={-90}
      />
      <directionalLight position={[-28, 18, -22]} intensity={0.32} color={PALETTE.slate} />

      <PaperGround span={viewSpan} />
      {softShadow && (
        <ContactShadows
          position={[0, 0.018, 0]}
          opacity={0.14}
          scale={Math.max(90, viewSpan * 0.9)}
          blur={2.8}
          far={18}
          color={PALETTE.ink}
        />
      )}

      {footprints.length > 0 && (
        <OsmFootprints
          features={footprints}
          project={projectLatLng}
          anchors={anchors}
          maxDist={corridorDist}
          onBaked={onBaked}
        />
      )}
      <RouteRibbon points={path} />

      {lanes.map((l) => (
        <group key={l.id} position={[l.x, 0, l.z]} rotation={[0, l.rot, 0]}>
          <LaneHouse w={l.w} d={l.d} h={l.h} seed={l.seed} />
        </group>
      ))}

      {trees.map((t) => (
        <group key={t.id} position={[t.x, 0, t.z]}>
          <PlaneTree scale={t.scale} />
        </group>
      ))}

      {stops.map((s) => (
        <StopMarker
          key={s.order}
          site={s}
          active={s.order === activeOrder}
          onSelect={() => onSelectStop(s.order)}
        />
      ))}

      <OrbitControls
        makeDefault
        enablePan={false}
        minPolarAngle={Math.PI / 3.05}
        maxPolarAngle={Math.PI / 2.45}
        minDistance={camDist * 0.45}
        maxDistance={camDist * 1.55}
        target={target}
        enableDamping
        dampingFactor={0.055}
      />
    </>
  );
}

type SceneProps = Props & {
  footprints?: FootprintFeature[];
  osmNote?: string;
};

export function MapScene25D(props: SceneProps) {
  const { envelope, footprints: preloaded, osmNote: preloadedNote } = props;
  const { span } = useMemo(() => projectStops(envelope), [envelope]);
  const camDist = Math.max(62, span * 0.82);
  const hasPreload = preloaded !== undefined;
  const perf = usePerfProfile();
  const [footprints, setFootprints] = useState<FootprintFeature[]>(
    preloaded ?? [],
  );
  const [baseNote, setBaseNote] = useState(
    preloadedNote ?? "正在烘焙 OSM 城景…",
  );
  const [bakeNote, setBakeNote] = useState("");
  const [bakeRadius, setBakeRadius] = useState(80);
  const [bakeCenter, setBakeCenter] = useState<[number, number, number]>([
    0, 3, 0,
  ]);

  const onBaked = useCallback((stats: BakeStats | null) => {
    if (!stats) {
      setBakeNote(footprints.length ? " · 烘焙未出块，已保留意象楼" : "");
      return;
    }
    setBakeNote(` · 可见 ${stats.count} 栋`);
    setBakeRadius(Math.max(60, stats.radius));
    setBakeCenter(stats.center);
  }, [footprints.length]);

  useEffect(() => {
    if (hasPreload) {
      setFootprints(preloaded ?? []);
      setBaseNote(preloadedNote ?? "");
      return;
    }
    let cancelled = false;
    (async () => {
      const bundle = await fetchFootprints(envelope);
      if (cancelled) return;
      setFootprints(bundle.features);
      setBaseNote(bundle.note);
    })();
    return () => {
      cancelled = true;
    };
  }, [envelope, hasPreload, preloaded, preloadedNote]);

  const caption = `${baseNote}${bakeNote}`;

  return (
    <div className="map-canvas map-canvas-25d" aria-label="海派 2.5D 城景">
      <Canvas
        shadows={perf.softShadow || !perf.mobile}
        dpr={perf.dpr}
        camera={{
          position: [camDist * 0.78, camDist * 0.52, camDist * 0.78],
          fov: 34,
          near: 0.5,
          far: 800,
        }}
        gl={{
          antialias: !perf.mobile,
          alpha: false,
          powerPreference: "high-performance",
          stencil: false,
        }}
        performance={{ min: 0.55 }}
      >
        <Suspense fallback={null}>
          <Scene
            {...props}
            footprints={footprints}
            softShadow={perf.softShadow}
            shadowMap={perf.shadowMap}
            onBaked={onBaked}
            bakeRadius={bakeRadius}
            bakeCenter={bakeCenter}
          />
        </Suspense>
      </Canvas>
      <div className="map25-caption">{caption}</div>
    </div>
  );
}
