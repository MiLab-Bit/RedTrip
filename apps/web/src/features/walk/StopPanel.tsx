import type { RouteEnvelope, RouteStop, SourceRef } from "@redtrip/contracts";
import {
  datasetLabel,
  shortRecordId,
  sourceHeadline,
} from "./sourceLabels";
import { ProvenanceBody, findStopClaims } from "./SentenceProvenance";

const ACT_LABEL: Record<string, string> = {
  prologue: "序章",
  focus: "聚焦",
  transit: "过渡",
  epilogue: "跋",
};

type Props = {
  envelope: RouteEnvelope;
  stop: RouteStop;
  source: SourceRef | null;
  onOpenSource: (source: SourceRef) => void;
  onCloseSource: () => void;
  /** split = story column only (timeline/nav live in WalkStage) */
  layout?: "full" | "split";
  onPrev?: () => void;
  onNext?: () => void;
  onFinish?: () => void;
  onBackMap?: () => void;
};

function SourceDrawer({
  source,
  onClose,
}: {
  source: SourceRef;
  onClose: () => void;
}) {
  const excerpt =
    source.excerpt?.trim() ||
    "本条未附原文摘录；记录编号可在上海图书馆开放数据中核对。";
  return (
    <div className="drawer source-drawer" role="dialog" aria-label="出处详情">
      <div className="source-drawer-head">
        <strong>{sourceHeadline(source)}</strong>
        <button className="btn secondary" type="button" onClick={onClose}>
          关闭
        </button>
      </div>
      <p className="source-excerpt">{excerpt}</p>
      <dl className="source-meta">
        <div>
          <dt>数据集</dt>
          <dd>{datasetLabel(source.dataset)}</dd>
        </div>
        <div>
          <dt>记录</dt>
          <dd>
            <code title={source.record_id}>{shortRecordId(source.record_id)}</code>
          </dd>
        </div>
      </dl>
      {source.record_id.startsWith("http") && (
        <a
          className="source-link"
          href={source.record_id}
          target="_blank"
          rel="noreferrer"
        >
          在浏览器打开原记录
        </a>
      )}
    </div>
  );
}

export function StopPanel({
  envelope,
  stop,
  source,
  onOpenSource,
  onCloseSource,
  layout = "full",
  onPrev,
  onNext,
  onFinish,
  onBackMap,
}: Props) {
  const story = envelope.blocks.find(
    (b) => b.type === "story_card" && b.stop_order === stop.order,
  );
  const essay = envelope.blocks.find(
    (b) => b.type === "essay" && b.stop_order === stop.order,
  );
  const scene = envelope.blocks.find(
    (b) => b.type === "scene" && b.stop_order === stop.order,
  );

  const storyClaims =
    story && story.type === "story_card"
      ? findStopClaims(envelope, stop.order, "story_card")
      : [];

  const isLast = stop.order >= envelope.route.stops.length;
  const people = stop.layers.filter((l) => l.kind === "person");
  const split = layout === "split";

  return (
    <section className={`panel stop-panel${split ? " is-split" : ""}`}>
      <p className="note stop-kicker">
        第 {stop.order} / {envelope.route.stops.length} 站 · 驻足约 {stop.minutes}{" "}
        分钟
        {stop.geo.precision !== "exact" ? " · 坐标示意" : ""}
        {stop.evidence_channel ? (
          <>
            {" · "}
            <span
              className={`channel-badge is-${stop.evidence_channel}`}
              title="证据通道"
            >
              {stop.evidence_channel === "slc" ? (
                <>
                  <span className="kite-seal-mini" aria-hidden>
                    鸢
                  </span>{" "}
                  馆藏
                </>
              ) : stop.evidence_channel === "landmark" ? (
                "地标词库"
              ) : stop.evidence_channel === "osm" ? (
                "OSM"
              ) : stop.evidence_channel === "amap" ? (
                "地图"
              ) : (
                "人工"
              )}
            </span>
          </>
        ) : null}
        {stop.act ? (
          <>
            {" · "}
            <span className={`act-badge is-${stop.act}`} title="规划节奏">
              {ACT_LABEL[stop.act] ?? stop.act}
            </span>
          </>
        ) : null}
      </p>
      <h2>{stop.name}</h2>
      <p className="lead stop-meaning">{stop.meaning}</p>

      {people.length > 0 && (
        <div className="cast-row">
          <span className="scene-label">本站人物</span>
          <div className="cast-chips">
            {people.map((p) => (
              <button
                key={p.label + p.source.record_id}
                className="cast-chip"
                type="button"
                onClick={() => onOpenSource(p.source)}
              >
                {p.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {story && story.type === "story_card" && (
        <article className="story-card">
          <h3>{story.title}</h3>
          <ProvenanceBody
            body={story.body}
            claims={storyClaims}
          />
          {story.age_parallel && <p className="age">{story.age_parallel}</p>}
          <div className="source-chip-row">
            <span className="source-chip-label">本站出处</span>
            {story.sources.slice(0, 4).map((s) => (
              <button
                key={s.dataset + s.record_id}
                className="source-chip"
                type="button"
                onClick={() => onOpenSource(s)}
              >
                {datasetLabel(s.dataset)}
              </button>
            ))}
          </div>
        </article>
      )}

      {essay && essay.type === "essay" && essay.body.trim() && (
        <details className="essay-panel">
          <summary>
            深读 · 长散文
            <span className="essay-len">{essay.body.trim().length} 字</span>
          </summary>
          {essay.title ? <h3 className="essay-title">{essay.title}</h3> : null}
          <div className="essay-body">
            {essay.body
              .split(/\n{2,}/)
              .map((p) => p.trim())
              .filter(Boolean)
              .map((p, i) => (
                <p key={i}>{p}</p>
              ))}
          </div>
        </details>
      )}

      <div className="pitfalls-block" aria-label="避坑信息">
        <span className="scene-label">避坑（未知写未收录）</span>
        <ul className="pitfalls-list">
          {(
            [
              ["开放时间", stop.pitfalls.open_hours],
              ["可否入内", stop.pitfalls.enterable],
              ["是否预约", stop.pitfalls.need_reservation],
            ] as const
          ).map(([label, value]) => {
            const honest = !value || value.includes("未收录");
            return (
              <li
                key={label}
                className={honest ? "pitfall is-unknown" : "pitfall"}
              >
                <strong>{label}</strong>
                <span>{value || "未收录"}</span>
              </li>
            );
          })}
        </ul>
        {stop.buri ? (
          <p className="buri-line">
            馆藏 URI：{" "}
            <a href={stop.buri} target="_blank" rel="noreferrer">
              {stop.buri}
            </a>
          </p>
        ) : (
          <p className="buri-line is-unknown">馆藏 URI：未收录</p>
        )}
      </div>

      {scene && scene.type === "scene" && (
        <div className={`scene-grid${split ? " scene-grid-compact" : ""}`}>
          <div>
            <span className="scene-label">舞台</span>
            <p>{scene.place}</p>
          </div>
          <div>
            <span className="scene-label">此刻</span>
            <p>{scene.today}</p>
          </div>
          {!split && (
            <>
              <div className="scene-span">
                <span className="scene-label">情节（馆藏时间线）</span>
                <p>{scene.era_desc}</p>
              </div>
              <div>
                <span className="scene-label">人物</span>
                <p>{scene.figures}</p>
              </div>
              <div>
                <span className="scene-label">站位</span>
                <p>{scene.visual_note}</p>
              </div>
            </>
          )}
          {split && (
            <div className="scene-span">
              <span className="scene-label">站位</span>
              <p>{scene.visual_note}</p>
            </div>
          )}
        </div>
      )}

      {stop.transition_to_next && (
        <p className="transition-note">
          <span>下一站怎么接</span>
          {stop.transition_to_next}
        </p>
      )}

      {source && <SourceDrawer source={source} onClose={onCloseSource} />}

      {!split && (
        <nav className="toc-actions" style={{ marginTop: "1rem" }} aria-label="漫步翻页">
          <button type="button" className="toc-action" onClick={onBackMap}>
            回总览
          </button>
          <span className="toc-action-sep" aria-hidden>
            ·
          </span>
          <button
            type="button"
            className="toc-action"
            onClick={onPrev}
            disabled={stop.order <= 1}
          >
            上一站
          </button>
          <span className="toc-action-sep" aria-hidden>
            ·
          </span>
          {!isLast ? (
            <button type="button" className="toc-action primary" onClick={onNext}>
              下一站
            </button>
          ) : (
            <button type="button" className="toc-action primary" onClick={onFinish}>
              收尾
            </button>
          )}
          <span className="toc-action-sep" aria-hidden>
            ·
          </span>
          <button type="button" className="toc-action" onClick={onFinish}>
            就此结束
          </button>
        </nav>
      )}
    </section>
  );
}
