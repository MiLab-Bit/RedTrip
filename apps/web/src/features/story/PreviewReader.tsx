import type { RouteEnvelope } from "@redtrip/contracts";
import { buildStoryView } from "./storyView";

/**
 * B4 章节级流式·预览阅读器。
 *
 * 策展还在后台润色时，用「模板 envelope + 已就绪的润色卡」先行阅读：
 * - 章节轨来自 curated_story（模板章节元数据）
 * - 正文来自 blocks 中对应 stop_order 的 story_card
 * - 已收到 chapter_ready 的章显示「已润色」，未收到的显示「润色生成中」
 *   （仍可读模板正文，不是占位）
 *
 * 这是预览态组件，不做复杂交互（无地图/无来源抽屉），
 * done 后由正式 WalkStage 接管。
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
  const cardBlock = (envelope.blocks ?? []).find(
    (b) => b.type === "story_card" && b.stop_order === stopOrder,
  );
  // find 不保留 discriminated union 窄化，手动收窄一次
  const card = cardBlock && cardBlock.type === "story_card" ? cardBlock : undefined;
  const polished = streamed[stopOrder] === true;

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

      <article className="prose preview-body">
        <h2>{card?.title ?? ch?.title ?? ""}</h2>
        {card?.body ? (
          <p>{card.body}</p>
        ) : (
          <p className="note">正文生成中…</p>
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
