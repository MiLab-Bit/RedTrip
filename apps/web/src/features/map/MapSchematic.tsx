import type { RouteEnvelope } from "@redtrip/contracts";

type Props = {
  envelope: RouteEnvelope;
  activeOrder?: number;
  onSelectStop: (order: number) => void;
};

function project(lat: number, lng: number, envelope: RouteEnvelope) {
  const lats = envelope.route.stops.map((s) => s.geo.lat);
  const lngs = envelope.route.stops.map((s) => s.geo.lng);
  const minLat = Math.min(...lats);
  const maxLat = Math.max(...lats);
  const minLng = Math.min(...lngs);
  const maxLng = Math.max(...lngs);
  const pad = 0.12;
  const w = maxLng - minLng || 0.01;
  const h = maxLat - minLat || 0.01;
  const x = ((lng - minLng) / w) * (1 - pad * 2) + pad;
  const y = 1 - (((lat - minLat) / h) * (1 - pad * 2) + pad);
  return { x: x * 100, y: y * 100 };
}

export function MapSchematic({ envelope, activeOrder, onSelectStop }: Props) {
  const points = envelope.route.stops.map((s) => ({
    stop: s,
    ...project(s.geo.lat, s.geo.lng, envelope),
  }));

  const poly = points.map((p) => `${p.x},${p.y}`).join(" ");

  return (
    <div className="map-canvas" aria-label="路线示意图">
      <svg viewBox="0 0 100 100" role="img">
        <polyline
          points={poly}
          fill="none"
          stroke="#A8322A"
          strokeWidth="1.2"
          strokeLinecap="round"
          strokeLinejoin="round"
          opacity="0.85"
        />
        {points.map(({ stop, x, y }) => {
          const active = stop.order === activeOrder;
          return (
            <g
              key={stop.whitelist_id}
              style={{ cursor: "pointer" }}
              onClick={() => onSelectStop(stop.order)}
            >
              <circle
                cx={x}
                cy={y}
                r={active ? 3.2 : 2.4}
                fill={active ? "#A8322A" : "#33333A"}
                stroke="#F2EBDD"
                strokeWidth="0.6"
              />
              <text
                x={x}
                y={y - 4}
                textAnchor="middle"
                fontSize="3.2"
                fill="#33333A"
                fontFamily="Noto Serif SC, serif"
              >
                {stop.order}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
