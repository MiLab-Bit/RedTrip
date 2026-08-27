import type { RouteStop, SourceRef } from "@redtrip/contracts";
import { kindLabel } from "./sourceLabels";

type Props = {
  stop: RouteStop;
  onOpenSource: (source: SourceRef) => void;
};

function yearOf(claim: string): string {
  const m = claim.match(/\d{3,4}/);
  return m ? m[0] : "·";
}

export function EventTimelineRail({ stop, onOpenSource }: Props) {
  const events = stop.layers.filter((l) => l.kind === "event").slice(0, 8);
  if (events.length === 0) {
    return (
      <div className="tl-rail empty">
        <span className="tl-rail-label">情节时间轴</span>
        <p className="note">此站暂无事件记载可排成时间轴。</p>
      </div>
    );
  }

  return (
    <div className="tl-rail">
      <div className="tl-rail-head">
        <span className="tl-rail-label">情节时间轴 · {stop.name}</span>
        <span className="note">左右滑动 · 点卡片查出处</span>
      </div>
      <ol className="tl-rail-track">
        {events.map((layer, idx) => (
          <li key={`${layer.label}-${idx}`} className="tl-rail-card">
            <button
              type="button"
              className="tl-rail-card-btn"
              onClick={() => onOpenSource(layer.source)}
            >
              <span className="tl-rail-year">{yearOf(layer.claim)}</span>
              <span className="tl-rail-kind">{kindLabel(layer.kind)}</span>
              <span className="tl-rail-title">{layer.label}</span>
              <p className="tl-rail-claim">{layer.claim}</p>
            </button>
            {idx < events.length - 1 && <span className="tl-rail-connector" aria-hidden />}
          </li>
        ))}
      </ol>
    </div>
  );
}
