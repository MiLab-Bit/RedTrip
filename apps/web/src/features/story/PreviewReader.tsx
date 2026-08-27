import type { RouteEnvelope } from "@redtrip/contracts";
import { buildStoryView } from "./storyView";
import { ProvenanceBody, findStopClaims } from "../walk/SentenceProvenance";
import { datasetLabel, channelLabel } from "../walk/sourceLabels";

/**
 * B4 章节级流式·预览阅读器。
 *
 * 策展还在后台润色时，用「模板 envelope + 已就绪的润色卡」先行阅读：
 * - 章节轨来自 curated_story（模板章节元数据）
 * - 正文来自 blocks 中对应 stop_order 的 story_card
 * - 排版与 WalkStage StopPanel 同源（ProvenanceBody + story-card）
 */
export function PreviewReader({
  envelope,
  streamed,
  currentChapter,
  onOpenChapter,
  onPrev,
  onNext,
  onBack,
}: {
  envelope: RouteEnvelope;
  streamed: Record<number, boolean>;
  currentChapter: number;
  onOpenChapter: (index: number) => void;
  onPrev: () => void;
  onNext: () => void;
  onBack: () => void;
}) {
  const view = buildStoryView(envelope);
  const chapters = view.chapters;
  const max = Math.max(1, chapters.length);
  const idx = Math.min(Math.max(1, currentChapter), max);
  const ch = chapters[idx - 1];
  const stopOrder = ch?.stopId ?? idx;
  const stop = envelope.route.stops.find((s) => s.order === stopOrder);
  const cardBlock = (envelope.blocks ?? []).find(
    (b) => b.type === "story_card" && b.stop_order === stopOrder,
  );
  const card = cardBlock && cardBlock.type === "story_card" ? cardBlock : undefined;
  const polished = streamed[stopOrder] === true;
  const storyClaims = card ? findStopClaims(envelope, stopOrder, "story_card") : [];

  return (
    <section className="book-page-flat preview-reader" aria-label="预览阅读">
      <div className="preview-topbar">
        <button type="button" className="btn btn-ghost" onClick={onBack}>
          ← 序章
        </button>
        <span className="preview-hint">
          {polished ? "本章已润色" : "模板预览 · 润色生成中"}
        </span>
        <span className="preview-progress">
          第 {idx}/{max} 章
        </span>
      </div>

      <nav className="preview-rail" aria-label="章节轨">
        {chapters.map((c, i) => (
          <button
            key={c.id}
            type="button"
            className={`preview-rail-item${i + 1 === idx ? " is-active" : ""}`}
            onClick={() => onOpenChapter(i + 1)}
          >
            <span className="preview-rail-no">{c.index}</span>
            <span className="preview-rail-title">{c.title}</span>
            {streamed[c.stopId] === true && (
              <span className="preview-badge">已润色</span>
            )}
          </button>
        ))}
      </nav>

      {stop && (
        <p className="note stop-kicker preview-kicker">
          第 {stop.order} / {envelope.route.stops.length} 站 · 驻足约 {stop.minutes}{" "}
          分钟
          {stop.evidence_channel ? (
            <>
              {" · "}
              <span className={`channel-badge is-${stop.evidence_channel}`}>
                {channelLabel(stop.evidence_channel)}
              </span>
            </>
          ) : null}
        </p>
      )}

      <article className="story-card preview-body">
        <h2>{card?.title ?? ch?.title ?? ""}</h2>
        {card?.body ? (
          <ProvenanceBody body={card.body} claims={storyClaims} />
        ) : (
          <p className="note">正文生成中…</p>
        )}
        {card?.age_parallel && <p className="age">{card.age_parallel}</p>}
        {card?.sources && card.sources.length > 0 && (
          <div className="source-chip-row">
            <span className="source-chip-label">本章出处</span>
            {card.sources.slice(0, 4).map((s) => (
              <span key={s.dataset + s.record_id} className="source-chip is-static">
                {datasetLabel(s.dataset)}
              </span>
            ))}
          </div>
        )}
      </article>

      <div className="btn-row preview-nav">
        <button
          type="button"
          className="btn"
          disabled={idx <= 1}
          onClick={onPrev}
        >
          上一章
        </button>
        <button
          type="button"
          className="btn"
          disabled={idx >= max}
          onClick={onNext}
        >
          下一章
        </button>
      </div>
    </section>
  );
}
