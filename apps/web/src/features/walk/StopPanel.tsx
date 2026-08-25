import type { RouteEnvelope, RouteStop, SourceRef } from "@redtrip/contracts";
import {
  datasetLabel,
  shortRecordId,
  sourceHeadline,
} from "./sourceLabels";
import { ProvenanceBody, findStopClaims } from "./SentenceProvenance";
import {
  ClassicalLayer,
  stopClassicalLayers,
  chapterClassicalFacts,
} from "./ClassicalLayer";

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

  // 典籍发掘：本站 classical 层 + 本章 classical 事实（来自 evidence_graph）
  const classicalLayers = stopClassicalLayers(envelope, stop.order);
  const classicalFacts = chapterClassicalFacts(envelope, []);
  const hasClassical = classicalLayers.length > 0 || classicalFacts.length > 0;

  return (
    <section className={`panel stop-panel${split ? " is-split" : ""}`}>
      <p className="note stop-kicker">
        第 {stop.order} / {envelope.route.stops.length} 站 · 驻足约 {stop.minutes}{" "}
        分钟
        {stop.geo.precision !== "exact" ? " · 坐标示意" : ""}
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

      {hasClassical && (
        <ClassicalLayer
          envelope={envelope}
          classicalLayers={classicalLayers}
          classicalFacts={classicalFacts}
          onOpenSource={onOpenSource}
        />
      )}

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
