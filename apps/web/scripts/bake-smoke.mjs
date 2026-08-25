import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import * as THREE from "three";
import { mergeGeometries } from "three/addons/utils/BufferGeometryUtils.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, "../../..");
const raw = JSON.parse(
  fs.readFileSync(path.join(root, "content/fixtures/osm-wukang.json"), "utf8"),
);

// Simulate API clip: corridor around stops
const stops = [
  [31.215026, 121.447147],
  [31.217898, 121.444543],
  [31.2152, 121.446466],
  [31.21749, 121.44771],
  [31.215746, 121.446986],
  [31.21242, 121.445595],
];
const pad = 0.0022;
const south = Math.min(...stops.map((s) => s[0])) - pad;
const north = Math.max(...stops.map((s) => s[0])) + pad;
const west = Math.min(...stops.map((s) => s[1])) - pad;
const east = Math.max(...stops.map((s) => s[1])) + pad;

const feats = raw.features.filter((f) => {
  const ring = f.geometry.coordinates[0];
  let la = 0,
    ln = 0;
  for (const c of ring) {
    ln += c[0];
    la += c[1];
  }
  la /= ring.length;
  ln /= ring.length;
  return south <= la && la <= north && west <= ln && ln <= east;
});

const lat0 = stops.reduce((a, s) => a + s[0], 0) / stops.length;
const lng0 = stops.reduce((a, s) => a + s[1], 0) / stops.length;
const mPerDegLat = 111320;
const mPerDegLng = 111320 * Math.cos((lat0 * Math.PI) / 180);
const project = (lat, lng) => ({
  x: (lng - lng0) * mPerDegLng,
  z: -((lat - lat0) * mPerDegLat),
});
const anchors = stops.map(([lat, lng]) => project(lat, lng));
const maxDist = 180;
const parts = [];

for (let i = 0; i < feats.length; i++) {
  const ring = feats[i].geometry.coordinates[0];
  const pts = ring.map((c) => project(c[1], c[0]));
  if (Math.hypot(pts[0].x - pts.at(-1).x, pts[0].z - pts.at(-1).z) > 1e-4) {
    pts.push({ ...pts[0] });
  }
  let a = 0;
  for (let j = 0; j < pts.length - 1; j++) {
    a += pts[j].x * pts[j + 1].z - pts[j + 1].x * pts[j].z;
  }
  a = Math.abs(a * 0.5);
  if (a < 5 || a > 4000) continue;
  let cx = 0,
    cz = 0;
  for (const p of pts) {
    cx += p.x;
    cz += p.z;
  }
  cx /= pts.length;
  cz /= pts.length;
  if (!anchors.some((an) => Math.hypot(cx - an.x, cz - an.z) <= maxDist)) continue;

  const shape = new THREE.Shape();
  pts.forEach((p, j) => (j ? shape.lineTo(p.x, -p.z) : shape.moveTo(p.x, -p.z)));
  shape.closePath();
  const geo = new THREE.ExtrudeGeometry(shape, {
    depth: 8,
    bevelEnabled: false,
    steps: 1,
    curveSegments: 1,
  });
  const pos = geo.getAttribute("position");
  for (let k = 0; k < pos.count; k++) {
    const x = pos.getX(k);
    const yShape = pos.getY(k);
    const zExt = pos.getZ(k);
    pos.setXYZ(k, x, zExt + 0.05, -yShape);
  }
  pos.needsUpdate = true;
  geo.computeVertexNormals();
  geo.clearGroups();
  geo.deleteAttribute("uv");
  const n = pos.count;
  const col = new Float32Array(n * 3);
  col.fill(0.85);
  geo.setAttribute("color", new THREE.BufferAttribute(col, 3));
  parts.push(geo);
  if (parts.length >= 80) break;
}

const merged = mergeGeometries(parts, false);
merged?.computeBoundingBox();
const bb = merged?.boundingBox;
console.log(
  JSON.stringify(
    {
      clipped: feats.length,
      parts: parts.length,
      merged: !!merged,
      verts: merged?.getAttribute("position")?.count ?? 0,
      bb: bb && {
        min: [+bb.min.x.toFixed(1), +bb.min.y.toFixed(1), +bb.min.z.toFixed(1)],
        max: [+bb.max.x.toFixed(1), +bb.max.y.toFixed(1), +bb.max.z.toFixed(1)],
      },
    },
    null,
    2,
  ),
);
