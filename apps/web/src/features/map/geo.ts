import type { RouteEnvelope, RouteStop } from "@redtrip/contracts";

export type Vec2 = { x: number; z: number };

export type LocalProjector = {
  lat0: number;
  lng0: number;
  project: (lat: number, lng: number) => Vec2;
  span: number;
  points: Array<{ stop: RouteStop; x: number; z: number }>;
};

/** Project WGS84 to local meters relative to route centroid (approx). */
export function projectStops(envelope: RouteEnvelope): LocalProjector {
  const stops = envelope.route.stops;
  const lat0 =
    stops.reduce((a, s) => a + s.geo.lat, 0) / Math.max(1, stops.length);
  const lng0 =
    stops.reduce((a, s) => a + s.geo.lng, 0) / Math.max(1, stops.length);
  const mPerDegLat = 111_320;
  const mPerDegLng = 111_320 * Math.cos((lat0 * Math.PI) / 180);

  const project = (lat: number, lng: number): Vec2 => ({
    x: (lng - lng0) * mPerDegLng,
    z: -((lat - lat0) * mPerDegLat),
  });

  const points = stops.map((stop) => ({
    stop,
    ...project(stop.geo.lat, stop.geo.lng),
  }));

  let maxR = 40;
  for (const p of points) {
    maxR = Math.max(maxR, Math.hypot(p.x, p.z));
  }

  return {
    lat0,
    lng0,
    project,
    points,
    span: maxR * 2.4,
  };
}

export function lerp(a: number, b: number, t: number) {
  return a + (b - a) * t;
}
