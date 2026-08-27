import type { RouteStop, SourceRef } from "@redtrip/contracts";
import { kindLabel } from "./sourceLabels";

type Props = {
  stop: RouteStop;
  onOpenSource: (source: SourceRef) => void;
};

const LAYER_ORDER = [
  "building",
  "person",
  "event",
  "era",
  "poem",
  "geoname",
  "literary",
] as const;

/**
 * 轻量关系图（非 Neo4j）：以当前站为中心，把 building / person / event 等层
 * 画成可点击的关系星形，服务「一栋楼的多重人生」口播。
 */
export function RelationGraph({ stop, onOpenSource }: Props) {
  const layers = [...stop.layers].sort(
    (a, b) =>
      LAYER_ORDER.indexOf(a.kind as (typeof LAYER_ORDER)[number]) -
      LAYER_ORDER.indexOf(b.kind as (typeof LAYER_ORDER)[number]),
  );
  if (layers.length === 0) {
    return (
      <div className="relation-graph empty">
        <span className="scene-label">本站关系</span>
        <p className="note">此站暂无多层身份可连。</p>
      </div>
    );
  }

  const cx = 160;
  const cy = 110;
  const r = 72;
  const nodes = layers.map((layer, i) => {
    const angle = (-Math.PI / 2) + (i * 2 * Math.PI) / layers.length;
    return {
      layer,
      x: cx + r * Math.cos(angle),
      y: cy + r * Math.sin(angle),
    };
  });

  return (
    <div className="relation-graph" aria-label="本站关系图">
      <div className="relation-graph-head">
        <span className="scene-label">本站关系 · 建筑 × 人物 × 事件</span>
        <span className="note">点节点查出处</span>
      </div>
      <svg viewBox="0 0 320 220" className="relation-svg" role="img">
        <circle cx={cx} cy={cy} r="34" className="relation-hub" />
        <text x={cx} y={cy - 4} textAnchor="middle" className="relation-hub-title">
          {stop.name.length > 6 ? `${stop.name.slice(0, 6)}…` : stop.name}
        </text>
        <text x={cx} y={cy + 12} textAnchor="middle" className="relation-hub-sub">
          本站
        </text>
        {nodes.map(({ layer, x, y }) => (
          <g key={`${layer.kind}-${layer.label}`}>
            <line
              x1={cx}
              y1={cy}
              x2={x}
              y2={y}
              className="relation-edge"
            />
            <a
              href={layer.source.record_id.startsWith("http") ? layer.source.record_id : undefined}
              onClick={(e) => {
                e.preventDefault();
                onOpenSource(layer.source);
              }}
            >
              <circle cx={x} cy={y} r="22" className={`relation-node layer-${layer.kind}`} />
              <text x={x} y={y - 2} textAnchor="middle" className="relation-node-kind">
                {kindLabel(layer.kind)}
              </text>
              <text x={x} y={y + 11} textAnchor="middle" className="relation-node-label">
                {layer.label.length > 5 ? `${layer.label.slice(0, 5)}…` : layer.label}
              </text>
            </a>
          </g>
        ))}
      </svg>
      <ul className="relation-legend">
        {layers.map((layer) => (
          <li key={`${layer.kind}-${layer.label}`}>
            <button
              type="button"
              className="relation-legend-btn"
              onClick={() => onOpenSource(layer.source)}
            >
              <span className={`layer-badge layer-${layer.kind}`}>
                {kindLabel(layer.kind)}
              </span>
              <span>{layer.label}</span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
