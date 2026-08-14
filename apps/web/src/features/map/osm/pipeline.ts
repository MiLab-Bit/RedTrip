/**
 * OSM → 海派 2.5D bake
 * project → simplify → cull → extrude → (optional) merge
 */
import * as THREE from "three";
import { mergeGeometries } from "three/addons/utils/BufferGeometryUtils.js";
import { PALETTE } from "../buildings/HaipaiArchitecture";
import type { FootprintFeature } from "./types";

export type ProjectFn = (lat: number, lng: number) => { x: number; z: number };

export type BakeResult = {
  geometry: THREE.BufferGeometry;
  count: number;
  discarded: number;
  radius: number;
  center: [number, number, number];
};

const WALL_TONES = [PALETTE.rice, PALETTE.ochre] as const;
const ROOF_TONES = [PALETTE.slate, PALETTE.ink] as const;
const WALL_C = WALL_TONES.map((h) => new THREE.Color(h));
const ROOF_C = ROOF_TONES.map((h) => new THREE.Color(h));

function hash01(n: number) {
  const x = Math.sin(n * 12.9898) * 43758.5453;
  return x - Math.floor(x);
}

function signedArea(ring: Array<{ x: number; z: number }>): number {
  let a = 0;
  for (let i = 0; i < ring.length - 1; i++) {
    a += ring[i].x * ring[i + 1].z - ring[i + 1].x * ring[i].z;
  }
  return a * 0.5;
}

export function simplifyRing(
  pts: Array<{ x: number; z: number }>,
  epsilon: number,
): Array<{ x: number; z: number }> {
  if (pts.length <= 5 || epsilon <= 0) return pts;

  const closed =
    Math.hypot(
      pts[0].x - pts[pts.length - 1].x,
      pts[0].z - pts[pts.length - 1].z,
    ) < 1e-4;
  const open = closed ? pts.slice(0, -1) : pts.slice();
  if (open.length < 3) return pts;

  const keep = new Uint8Array(open.length);
  keep[0] = 1;
  keep[open.length - 1] = 1;

  const stack: Array<[number, number]> = [[0, open.length - 1]];
  while (stack.length) {
    const [start, end] = stack.pop()!;
    const ax = open[start].x;
    const az = open[start].z;
    const bx = open[end].x;
    const bz = open[end].z;
    const dx = bx - ax;
    const dz = bz - az;
    const len2 = dx * dx + dz * dz || 1;
    let maxDist = 0;
    let maxIdx = -1;
    for (let i = start + 1; i < end; i++) {
      const px = open[i].x;
      const pz = open[i].z;
      const t = ((px - ax) * dx + (pz - az) * dz) / len2;
      const qx = ax + t * dx;
      const qz = az + t * dz;
      const d = Math.hypot(px - qx, pz - qz);
      if (d > maxDist) {
        maxDist = d;
        maxIdx = i;
      }
    }
    if (maxDist > epsilon && maxIdx >= 0) {
      keep[maxIdx] = 1;
      stack.push([start, maxIdx], [maxIdx, end]);
    }
  }

  const out: Array<{ x: number; z: number }> = [];
  for (let i = 0; i < open.length; i++) {
    if (keep[i]) out.push(open[i]);
  }
  if (out.length < 3) return pts;
  out.push({ ...out[0] });
  return out;
}

function projectRing(
  f: FootprintFeature,
  project: ProjectFn,
): Array<{ x: number; z: number }> | null {
  const raw = f.geometry?.coordinates?.[0];
  if (!raw || raw.length < 4) return null;
  const pts: Array<{ x: number; z: number }> = [];
  for (const c of raw) {
    const lng = c[0];
    const lat = c[1];
    if (typeof lat !== "number" || typeof lng !== "number") continue;
    if (!Number.isFinite(lat) || !Number.isFinite(lng)) continue;
    pts.push(project(lat, lng));
  }
  if (pts.length < 4) return null;
  const first = pts[0];
  const last = pts[pts.length - 1];
  if (Math.hypot(first.x - last.x, first.z - last.z) > 1e-4) {
    pts.push({ ...first });
  }
  return pts;
}

function centroid(pts: Array<{ x: number; z: number }>) {
  let cx = 0;
  let cz = 0;
  const closed =
    Math.hypot(
      pts[0].x - pts[pts.length - 1].x,
      pts[0].z - pts[pts.length - 1].z,
    ) < 1e-4;
  const count = Math.max(1, pts.length - (closed ? 1 : 0));
  for (let i = 0; i < count; i++) {
    cx += pts[i].x;
    cz += pts[i].z;
  }
  return { cx: cx / count, cz: cz / count };
}

function heightFor(f: FootprintFeature, area: number, idx: number): number {
  const hProp = f.properties?.height_m;
  const levels = Number(f.properties?.levels);
  if (typeof hProp === "number" && hProp > 0) {
    return Math.min(16, Math.max(4, hProp * 0.78));
  }
  if (Number.isFinite(levels) && levels > 0) {
    return Math.min(14, Math.max(4, levels * 2.55));
  }
  return 4.4 + Math.min(6, Math.sqrt(Math.abs(area)) * 0.26) + hash01(idx) * 1.1;
}

function paintVertexColors(
  geo: THREE.BufferGeometry,
  wall: THREE.Color,
  roof: THREE.Color,
) {
  const pos = geo.getAttribute("position");
  const nrm = geo.getAttribute("normal");
  if (!pos || !nrm) return;
  const colors = new Float32Array(pos.count * 3);
  for (let i = 0; i < pos.count; i++) {
    const ny = nrm.getY(i);
    const c = ny > 0.42 ? roof : wall;
    const shade =
      ny > 0.42 ? 1 : 0.96 + Math.min(0.04, Math.abs(nrm.getX(i)) * 0.04);
    colors[i * 3] = c.r * shade;
    colors[i * 3 + 1] = c.g * shade;
    colors[i * 3 + 2] = c.b * shade;
  }
  geo.setAttribute("color", new THREE.BufferAttribute(colors, 3));
}

function ensureCCW(pts: Array<{ x: number; z: number }>) {
  if (signedArea(pts) < 0) {
    const closed =
      Math.hypot(
        pts[0].x - pts[pts.length - 1].x,
        pts[0].z - pts[pts.length - 1].z,
      ) < 1e-4;
    const body = closed ? pts.slice(0, -1) : pts.slice();
    body.reverse();
    body.push({ ...body[0] });
    return body;
  }
  return pts;
}

function extrudeRing(
  ptsIn: Array<{ x: number; z: number }>,
  h: number,
  wall: THREE.Color,
  roof: THREE.Color,
): THREE.BufferGeometry | null {
  const pts = ensureCCW(ptsIn);
  const shape = new THREE.Shape();
  pts.forEach((p, i) => {
    if (i === 0) shape.moveTo(p.x, -p.z);
    else shape.lineTo(p.x, -p.z);
  });
  shape.closePath();

  // Extrude along +Z then map to Y-up: avoids the old rotateX mirror quirks.
  const geo = new THREE.ExtrudeGeometry(shape, {
    depth: h,
    bevelEnabled: false,
    steps: 1,
    curveSegments: 1,
  });

  // shape (x, -z) extruded in +Z → remap to (x, y=extrude, z)
  const pos = geo.getAttribute("position") as THREE.BufferAttribute;
  for (let i = 0; i < pos.count; i++) {
    const x = pos.getX(i);
    const yShape = pos.getY(i); // was -z
    const zExt = pos.getZ(i); // height
    pos.setXYZ(i, x, zExt + 0.05, -yShape);
  }
  pos.needsUpdate = true;
  geo.computeVertexNormals();

  for (let i = 0; i < Math.min(pos.count, 24); i++) {
    if (!Number.isFinite(pos.getX(i)) || !Number.isFinite(pos.getY(i))) {
      geo.dispose();
      return null;
    }
  }
  if (pos.count < 9) {
    geo.dispose();
    return null;
  }

  paintVertexColors(geo, wall, roof);
  geo.clearGroups();
  // Drop uvs — keeps mergeGeometries consistent across parts
  geo.deleteAttribute("uv");
  return geo;
}

export type BakeOptions = {
  anchors?: Array<{ x: number; z: number }>;
  maxDist?: number;
  maxBuildings?: number;
  simplifyM?: number;
  minArea?: number;
  maxArea?: number;
};

type Cand = {
  pts: Array<{ x: number; z: number }>;
  area: number;
  cx: number;
  cz: number;
  h: number;
  idx: number;
  dist2: number;
};

function collectCandidates(
  features: FootprintFeature[],
  project: ProjectFn,
  opts: Required<
    Pick<
      BakeOptions,
      "anchors" | "maxDist" | "simplifyM" | "minArea" | "maxArea"
    >
  >,
): { cands: Cand[]; discarded: number } {
  const { anchors, maxDist, simplifyM, minArea, maxArea } = opts;
  const cands: Cand[] = [];
  let discarded = 0;

  for (let i = 0; i < features.length; i++) {
    const ring = projectRing(features[i], project);
    if (!ring) {
      discarded++;
      continue;
    }
    const pts = simplifyRing(ring, simplifyM);
    const area = Math.abs(signedArea(pts));
    if (area < minArea || area > maxArea) {
      discarded++;
      continue;
    }
    const { cx, cz } = centroid(pts);
    let dist2 = cx * cx + cz * cz;
    if (anchors.length > 0) {
      let best = Infinity;
      for (const a of anchors) {
        const d = (cx - a.x) ** 2 + (cz - a.z) ** 2;
        if (d < best) best = d;
      }
      if (best > maxDist * maxDist) {
        discarded++;
        continue;
      }
      dist2 = best;
    }
    cands.push({
      pts,
      area,
      cx,
      cz,
      h: heightFor(features[i], area, i),
      idx: i,
      dist2,
    });
  }
  cands.sort((a, b) => a.dist2 - b.dist2);
  return { cands, discarded };
}

function extrudeCandidates(cands: Cand[]): THREE.BufferGeometry[] {
  const parts: THREE.BufferGeometry[] = [];
  for (const c of cands) {
    const wall = WALL_C[c.idx % WALL_C.length];
    const roof = ROOF_C[c.idx % ROOF_C.length];
    const geo = extrudeRing(c.pts, c.h, wall, roof);
    if (geo) parts.push(geo);
  }
  return parts;
}

/**
 * Bake corridor footprints into one batched BufferGeometry.
 */
export function bakeFootprintBatch(
  features: FootprintFeature[],
  project: ProjectFn,
  opts: BakeOptions = {},
): BakeResult | null {
  const {
    anchors = [],
    maxDist = 220,
    maxBuildings = 80,
    simplifyM = 0.55,
    minArea = 5,
    maxArea = 4000,
  } = opts;

  let { cands, discarded } = collectCandidates(features, project, {
    anchors,
    maxDist,
    simplifyM,
    minArea,
    maxArea,
  });

  // If cull was too aggressive (fixture/live mismatch), relax once.
  if (cands.length < 8 && anchors.length > 0 && features.length >= 8) {
    const relaxed = collectCandidates(features, project, {
      anchors,
      maxDist: Math.max(maxDist * 2.2, 320),
      simplifyM,
      minArea,
      maxArea,
    });
    cands = relaxed.cands;
    discarded = relaxed.discarded;
  }

  const kept = cands.slice(0, maxBuildings);
  discarded += Math.max(0, cands.length - kept.length);
  const parts = extrudeCandidates(kept);
  if (parts.length === 0) return null;

  let merged: THREE.BufferGeometry | null = null;
  try {
    merged = mergeGeometries(parts, false);
  } catch {
    merged = null;
  }

  if (!merged) {
    // Manual concat fallback — never leave the city blank
    const positions: number[] = [];
    const normals: number[] = [];
    const colors: number[] = [];
    for (const g of parts) {
      const p = g.getAttribute("position");
      const n = g.getAttribute("normal");
      const c = g.getAttribute("color");
      for (let i = 0; i < p.count; i++) {
        positions.push(p.getX(i), p.getY(i), p.getZ(i));
        if (n) normals.push(n.getX(i), n.getY(i), n.getZ(i));
        else normals.push(0, 1, 0);
        if (c) colors.push(c.getX(i), c.getY(i), c.getZ(i));
        else colors.push(0.9, 0.85, 0.75);
      }
      g.dispose();
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute(
      "position",
      new THREE.Float32BufferAttribute(positions, 3),
    );
    geo.setAttribute("normal", new THREE.Float32BufferAttribute(normals, 3));
    geo.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));
    geo.computeBoundingSphere();
    geo.computeBoundingBox();
    const sp = geo.boundingSphere;
    return {
      geometry: geo,
      count: parts.length,
      discarded,
      radius: sp?.radius ?? 80,
      center: sp ? [sp.center.x, sp.center.y, sp.center.z] : [0, 3, 0],
    };
  }

  for (const g of parts) g.dispose();
  merged.computeBoundingSphere();
  merged.computeBoundingBox();
  const sp = merged.boundingSphere;
  return {
    geometry: merged,
    count: parts.length,
    discarded,
    radius: sp?.radius ?? 80,
    center: sp ? [sp.center.x, sp.center.y, sp.center.z] : [0, 3, 0],
  };
}
