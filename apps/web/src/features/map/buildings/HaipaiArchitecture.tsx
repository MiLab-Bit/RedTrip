import { Edges } from "@react-three/drei";
import { useEffect, useMemo } from "react";
import * as THREE from "three";

export const PALETTE = {
  ink: "#33333A",
  ochre: "#B9824F",
  slate: "#7C8A8D",
  rice: "#EDE4D3",
  vermilion: "#A8322A",
  xuan: "#F2EBDD",
} as const;

type Common = {
  active?: boolean;
  onSelect?: () => void;
};

function Mat({
  color,
  emissive,
}: {
  color: string;
  emissive?: string;
}) {
  return (
    <meshStandardMaterial
      color={color}
      emissive={emissive ?? "#000000"}
      emissiveIntensity={emissive ? 0.12 : 0}
      roughness={0.92}
      metalness={0}
      flatShading
    />
  );
}

function Outline({ threshold = 18 }: { threshold?: number }) {
  return <Edges threshold={threshold} color={PALETTE.ink} scale={1.002} />;
}

/** 石库门意象：台基 + 暖墙 + 门楣朱红 + 坡顶 */
export function ShikumenHero({
  w = 8.2,
  d = 6.4,
  stories = 3,
  active,
  onSelect,
}: Common & { w?: number; d?: number; stories?: number }) {
  const wallH = stories * 3.1;
  const roofH = 2.8;
  const y0 = 0.45;

  const windows = useMemo(() => {
    const items: Array<{ x: number; y: number }> = [];
    const cols = 3;
    const rows = Math.max(1, stories - 1);
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        if (r === 0 && c === 1) continue; // door bay
        items.push({
          x: (c - 1) * (w * 0.26),
          y: y0 + 3.4 + r * 2.9,
        });
      }
    }
    return items;
  }, [stories, w]);

  const wall = PALETTE.ochre;

  return (
    <group
      onClick={(e) => {
        e.stopPropagation();
        onSelect?.();
      }}
    >
      {/* 台基 */}
      <mesh position={[0, 0.22, 0]} castShadow receiveShadow>
        <boxGeometry args={[w * 1.08, 0.45, d * 1.08]} />
        <Mat color={PALETTE.ink} />
        <Outline />
      </mesh>

      {/* 墙身 */}
      <mesh position={[0, y0 + wallH / 2, 0]} castShadow receiveShadow>
        <boxGeometry args={[w, wallH, d]} />
        <Mat color={wall} />
        <Outline />
      </mesh>

      {/* 腰线 */}
      <mesh position={[0, y0 + wallH * 0.48, d / 2 + 0.04]} castShadow>
        <boxGeometry args={[w * 0.92, 0.18, 0.12]} />
        <Mat color={PALETTE.rice} />
      </mesh>

      {/* 门斗 */}
      <mesh position={[0, y0 + 1.35, d / 2 + 0.12]} castShadow>
        <boxGeometry args={[1.55, 2.55, 0.35]} />
        <Mat color={PALETTE.ink} />
        <Outline />
      </mesh>
      <mesh position={[0, y0 + 1.25, d / 2 + 0.32]} castShadow>
        <boxGeometry args={[1.15, 2.15, 0.12]} />
        <Mat color={PALETTE.vermilion} emissive={PALETTE.vermilion} />
      </mesh>
      {/* 门楣 */}
      <mesh position={[0, y0 + 2.85, d / 2 + 0.28]} castShadow>
        <boxGeometry args={[2.1, 0.35, 0.4]} />
        <Mat color={PALETTE.rice} />
        <Outline />
      </mesh>

      {/* 窗 */}
      {windows.map((p, i) => (
        <group key={i} position={[p.x, p.y, d / 2 + 0.06]}>
          <mesh castShadow>
            <boxGeometry args={[1.15, 1.35, 0.1]} />
            <Mat color={PALETTE.ink} />
          </mesh>
          <mesh position={[0, 0, 0.06]}>
            <boxGeometry args={[0.9, 1.05, 0.06]} />
            <Mat color={PALETTE.rice} />
          </mesh>
        </group>
      ))}

      {/* 檐口 */}
      <mesh position={[0, y0 + wallH + 0.18, 0]} castShadow>
        <boxGeometry args={[w * 1.14, 0.36, d * 1.14]} />
        <Mat color={PALETTE.rice} />
        <Outline />
      </mesh>

      {/* 四坡顶（方锥） */}
      <mesh
        position={[0, y0 + wallH + 0.35 + roofH / 2, 0]}
        rotation={[0, Math.PI / 4, 0]}
        castShadow
      >
        <coneGeometry args={[Math.max(w, d) * 0.78, roofH, 4]} />
        <Mat color={active ? PALETTE.ink : PALETTE.ink} />
        <Outline threshold={12} />
      </mesh>

      {/* 脊饰 / 选中时朱红旗杆感 */}
      <mesh position={[0, y0 + wallH + 0.35 + roofH + 0.25, 0]} castShadow>
        <boxGeometry args={[0.35, 0.5, 0.35]} />
        <Mat color={PALETTE.vermilion} />
      </mesh>
      {active && (
        <mesh position={[0, y0 + wallH + 0.35 + roofH + 1.1, 0]} castShadow>
          <cylinderGeometry args={[0.06, 0.06, 1.4, 6]} />
          <Mat color={PALETTE.vermilion} emissive={PALETTE.vermilion} />
        </mesh>
      )}
    </group>
  );
}

/** 花园洋房意象：更宽、退台、浅坡顶 */
export function VillaHero({
  w = 10,
  d = 7.2,
  active,
  onSelect,
}: Common & { w?: number; d?: number }) {
  const wallH = 8.5;
  const roofH = 3.2;
  const body = PALETTE.ochre;

  return (
    <group
      onClick={(e) => {
        e.stopPropagation();
        onSelect?.();
      }}
    >
      <mesh position={[0, 0.2, 0]} castShadow receiveShadow>
        <boxGeometry args={[w * 1.1, 0.4, d * 1.15]} />
        <Mat color={PALETTE.slate} />
        <Outline />
      </mesh>

      {/* 主楼 */}
      <mesh position={[0, 0.4 + wallH / 2, 0]} castShadow receiveShadow>
        <boxGeometry args={[w, wallH, d]} />
        <Mat color={body} />
        <Outline />
      </mesh>

      {/* 前廊 */}
      <mesh position={[0, 1.6, d / 2 + 0.9]} castShadow>
        <boxGeometry args={[w * 0.72, 0.25, 2.0]} />
        <Mat color={PALETTE.rice} />
        <Outline />
      </mesh>
      {[-1, 1].map((s) => (
        <mesh key={s} position={[s * w * 0.28, 0.95, d / 2 + 0.9]} castShadow>
          <cylinderGeometry args={[0.18, 0.22, 1.5, 8]} />
          <Mat color={PALETTE.rice} />
        </mesh>
      ))}

      {/* 二楼露台条 */}
      <mesh position={[0, 5.2, d / 2 + 0.15]} castShadow>
        <boxGeometry args={[w * 0.85, 0.22, 0.55]} />
        <Mat color={PALETTE.rice} />
      </mesh>

      {/* 窗排 */}
      {[-1, 0, 1].map((c) => (
        <group key={c}>
          {[3.2, 6.2].map((y) => (
            <mesh
              key={y}
              position={[c * w * 0.28, y, d / 2 + 0.05]}
              castShadow
            >
              <boxGeometry args={[1.4, 1.6, 0.12]} />
              <Mat color={PALETTE.rice} />
              <Outline threshold={20} />
            </mesh>
          ))}
        </group>
      ))}

      <mesh position={[0, 0.4 + wallH + 0.2, 0]} castShadow>
        <boxGeometry args={[w * 1.12, 0.4, d * 1.12]} />
        <Mat color={PALETTE.rice} />
        <Outline />
      </mesh>

      <mesh
        position={[0, 0.4 + wallH + 0.4 + roofH / 2, 0]}
        rotation={[0, Math.PI / 4, 0]}
        castShadow
      >
        <coneGeometry args={[Math.max(w, d) * 0.82, roofH, 4]} />
        <Mat color={PALETTE.ink} />
        <Outline threshold={12} />
      </mesh>
      {active && (
        <mesh position={[0, 0.4 + wallH + 0.4 + roofH + 0.9, 0]} castShadow>
          <cylinderGeometry args={[0.06, 0.06, 1.4, 6]} />
          <Mat color={PALETTE.vermilion} emissive={PALETTE.vermilion} />
        </mesh>
      )}
    </group>
  );
}

/** 走廊辅楼：克制青灰，不抢戏 */
export function LaneHouse({
  w = 4.2,
  d = 3.6,
  h = 5.5,
  seed = 0,
}: {
  w?: number;
  d?: number;
  h?: number;
  seed?: number;
}) {
  const hasAwning = seed % 3 !== 0;
  return (
    <group>
      <mesh position={[0, h / 2, 0]} castShadow receiveShadow>
        <boxGeometry args={[w, h, d]} />
        <Mat color={PALETTE.slate} />
        <Outline threshold={22} />
      </mesh>
      <mesh position={[0, h + 0.12, 0]} castShadow>
        <boxGeometry args={[w * 1.06, 0.24, d * 1.06]} />
        <Mat color={PALETTE.rice} />
      </mesh>
      {/* 一扇窗即可 */}
      <mesh position={[0, h * 0.55, d / 2 + 0.04]}>
        <boxGeometry args={[0.85, 1.0, 0.08]} />
        <Mat color={PALETTE.rice} />
      </mesh>
      {hasAwning && (
        <mesh
          position={[0, h * 0.72, d / 2 + 0.35]}
          rotation={[0.35, 0, 0]}
          castShadow
        >
          <boxGeometry args={[w * 0.7, 0.08, 0.7]} />
          <Mat color={PALETTE.ink} />
        </mesh>
      )}
    </group>
  );
}

/** 梧桐意象：仅用 6 色，青灰冠 + 墨干 */
export function PlaneTree({ scale = 1 }: { scale?: number }) {
  return (
    <group scale={scale}>
      <mesh position={[0, 1.1, 0]} castShadow={false}>
        <cylinderGeometry args={[0.12, 0.18, 2.2, 6]} />
        <Mat color={PALETTE.ink} />
      </mesh>
      <mesh position={[0, 2.6, 0]} castShadow={false}>
        <sphereGeometry args={[1.15, 8, 6]} />
        <Mat color={PALETTE.slate} />
        <Outline threshold={30} />
      </mesh>
      <mesh position={[0.45, 2.9, 0.2]} castShadow={false}>
        <sphereGeometry args={[0.7, 8, 6]} />
        <Mat color={PALETTE.slate} />
      </mesh>
    </group>
  );
}

/** 缎带路线：扁管，朱而不刺眼 */
export function RouteRibbon({
  points,
}: {
  points: Array<[number, number, number]>;
}) {
  const geom = useMemo(() => {
    if (points.length < 2) return null;
    const curve = new THREE.CatmullRomCurve3(
      points.map((p) => new THREE.Vector3(p[0], p[1], p[2])),
    );
    return new THREE.TubeGeometry(curve, 36, 0.38, 6, false);
  }, [points]);

  useEffect(() => {
    return () => {
      geom?.dispose();
    };
  }, [geom]);

  if (!geom) return null;
  return (
    <mesh geometry={geom} castShadow={false} receiveShadow>
      <meshStandardMaterial
        color={PALETTE.vermilion}
        roughness={0.82}
        metalness={0}
        flatShading
        emissive={PALETTE.vermilion}
        emissiveIntensity={0.06}
      />
    </mesh>
  );
}
