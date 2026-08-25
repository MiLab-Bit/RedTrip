import type { HongyuanMeta, RouteEnvelope } from "@redtrip/contracts";
import type { FootprintFeature } from "./Footprints";
import { MapCanvas } from "./MapCanvas";

type Props = {
  envelope: RouteEnvelope;
  assumptions: string[];
  hongyuan?: HongyuanMeta | null;
  footprints?: FootprintFeature[];
  osmNote?: string;
  activeOrder?: number;
  /** 作为子视图时提供：返回序章或阅读器 */
  onBack?: () => void;
  onOpenStop: (order: number) => void;
  onFinish: () => void;
  onRestart: () => void;
};

function readingLine(h: HongyuanMeta): string {
  if (h.summary) return h.summary;
  const parts = [
    h.emotion?.label,
    h.voice_style?.label,
    h.narrative?.label,
    h.knowledge_angle?.label,
    h.pacing?.label,
  ].filter(Boolean);
  return parts.length
    ? `${h.agent || "红鸢"}今日读法：${parts.join(" · ")}`
    : "";
}

export function MapStage({
  envelope,
  assumptions,
  hongyuan,
  footprints,
  osmNote,
  activeOrder,
  onBack,
  onOpenStop,
  onFinish,
  onRestart,
}: Props) {
  const hongyuanLine = hongyuan ? readingLine(hongyuan) : "";
  const hotwordLine =
    hongyuan?.layer3_summary ||
    (hongyuan?.layer3?.length
      ? `本周热词：${hongyuan.layer3
          .map((h) => h.term)
          .filter(Boolean)
          .slice(0, 3)
          .join(" · ")}`
      : "");
  const plainAssumptions = assumptions.filter(
    (a) => !a.startsWith("红鸢今日读法") && !a.startsWith("本周热词"),
  );

  return (
    <section className="panel book-page-flat map-stage">
      <h2>{envelope.theme}</h2>
      <p className="lead">{envelope.curator_note}</p>
      <p className="note">
        逻辑线：{envelope.logic_line}
        <br />
        约 {envelope.route.duration_min} 分钟 · 步行估{" "}
        {envelope.route.walk_meters_est} 米 · {envelope.scenario}
      </p>
      {hongyuanLine && (
        <p className="hongyuan-reading" title={hongyuan?.seed != null ? `seed ${hongyuan.seed}` : undefined}>
          {hongyuanLine}
        </p>
      )}
      {hotwordLine && (
        <p
          className="hongyuan-hotwords"
          title={hongyuan?.layer3_week ? `week ${hongyuan.layer3_week}` : undefined}
        >
          {hotwordLine}
        </p>
      )}
      {plainAssumptions.length > 0 && (
        <p className="assumptions">假设：{plainAssumptions.join("；")}</p>
      )}

      <div className="map-layout">
        <div>
          <MapCanvas
            envelope={envelope}
            activeOrder={activeOrder}
            onSelectStop={onOpenStop}
            footprints={footprints}
            osmNote={osmNote}
          />
          <p className="note" style={{ marginTop: "0.5rem" }}>
            可拖曳旋转 · 点击编号楼进站 · 走廊优先 OSM 真轮廓
          </p>
        </div>

        <aside className="toc">
          <p className="toc-label">目录</p>
          <ol className="toc-list">
            {envelope.route.stops.map((s) => (
              <li key={s.whitelist_id} className="toc-item">
                <button
                  type="button"
                  className="toc-link"
                  onClick={() => onOpenStop(s.order)}
                >
                  <span className="toc-num">
                    {String(s.order).padStart(2, "0")}
                  </span>
                  <span className="toc-body">
                    <span className="toc-name">{s.name}</span>
                    <span className="toc-dots" aria-hidden />
                    <span className="toc-min">{s.minutes}′</span>
                  </span>
                  <span className="toc-meaning">{s.meaning}</span>
                </button>
              </li>
            ))}
          </ol>
          <nav className="toc-actions" aria-label="目录操作">
            {onBack && (
              <>
                <button type="button" className="toc-action" onClick={onBack}>
                  ← 返回
                </button>
                <span className="toc-action-sep" aria-hidden>
                  ·
                </span>
              </>
            )}
            <button type="button" className="toc-action primary" onClick={() => onOpenStop(1)}>
              进入阅读
            </button>
            <span className="toc-action-sep" aria-hidden>
              ·
            </span>
            <button type="button" className="toc-action" onClick={onFinish}>
              直接收尾
            </button>
            <span className="toc-action-sep" aria-hidden>
              ·
            </span>
            <button type="button" className="toc-action" onClick={onRestart}>
              重新出题
            </button>
          </nav>
        </aside>
      </div>
    </section>
  );
}
