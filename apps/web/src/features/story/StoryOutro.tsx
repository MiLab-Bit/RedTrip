import { useMemo } from "react";
import type { RouteEnvelope, HongyuanMeta, CuratorReview } from "@redtrip/contracts";
import type { StoryView } from "./storyView";
import {
  buildBookDoc,
  exportPdf,
  exportEpub,
  type BookDoc,
} from "./exportBook";
import { ROLE_LABEL } from "./NarrativeMap";

type Props = {
  envelope: RouteEnvelope;
  storyView: StoryView;
  hongyuan?: HongyuanMeta | null;
  onRestart: () => void;
};

function datasetLabel(dataset: string): string {
  const map: Record<string, string> = {
    slc_building: "上图书目 · 建筑",
    slc_event: "上图事件",
    slc_person: "上图人物",
    slc_era: "纪年",
    slc_poem: "诗词",
    geoname: "地名志",
    literary: "文学交集",
    source: "出处",
  };
  return map[dataset] ?? dataset;
}

function hasReview(r: CuratorReview | null | undefined): boolean {
  if (!r) return false;
  return Boolean(
    (r.warnings && r.warnings.length) ||
      (r.concerns && r.concerns.length) ||
      (r.missed_voices && r.missed_voices.length) ||
      r.alternative_thesis ||
      r.reverse_route_note ||
      r.skipped_harder_node,
  );
}

export function StoryOutro({
  envelope,
  storyView,
  hongyuan,
  onRestart,
}: Props) {
  const doc: BookDoc = useMemo(
    () => buildBookDoc(envelope, storyView, hongyuan),
    [envelope, storyView, hongyuan],
  );

  const sources = useMemo(() => {
    const seen = new Set<string>();
    const out: { dataset: string; record_id: string }[] = [];
    for (const s of doc.sourcesIndex) {
      const key = `${s.dataset}::${s.record_id}`;
      if (!seen.has(key)) {
        seen.add(key);
        out.push(s);
      }
    }
    return out;
  }, [doc]);

  const review = envelope.curator_review;
  const showReview = hasReview(review);

  return (
    <section className="panel done-card book-page-flat">
      <p className="note story-kicker">城市记忆策展人 · 可溯源书页 · 跋</p>
      <h2>{storyView.themeTitle || envelope.theme}</h2>
      {doc.epilogue[0] && <p className="lead">{doc.epilogue[0]}</p>}
      {doc.epilogue.slice(1).map((p, i) => (
        <p className="note" key={i}>
          {p}
        </p>
      ))}

      <div className="done-toc">
        <p className="scene-label">这一程的章节</p>
        <ol>
          {storyView.chapters.map((c) => (
            <li key={c.id}>
              <span className={`role-badge role-${c.narrativeRole.toLowerCase()}`}>
                {ROLE_LABEL[c.narrativeRole]}
              </span>{" "}
              {c.title}
              {c.relationToPrevious ? (
                <span className="chapter-rel"> · ↳ {c.relationToPrevious}</span>
              ) : null}
            </li>
          ))}
        </ol>
      </div>

      {storyView.cast.length > 0 && (
        <div className="done-cast">
          <p className="scene-label">出场人物</p>
          <p>{storyView.cast.map((e) => e.name).join("、")}</p>
        </div>
      )}

      {showReview && review && (
        <div className="done-review curator-blank">
          <p className="scene-label">策展留白 · 反方策展人</p>
          <p className="note">
            以下为对抗性评审留下的未决问题，不构成定论；它们指向值得在下一版或现场继续追问的方向。
          </p>
          {review.warnings && review.warnings.length > 0 && (
            <div className="review-block">
              <p className="scene-label">评审告警</p>
              <ul>
                {review.warnings.map((w) => (
                  <li key={w}>{w}</li>
                ))}
              </ul>
            </div>
          )}
          {review.concerns && review.concerns.length > 0 && (
            <div className="review-block">
              <p className="scene-label">反对意见</p>
              <ul>
                {review.concerns.map((c, i) => (
                  <li key={`${c.node ?? "n"}-${i}`}>
                    <strong>{c.node || "全路线"}</strong>
                    {c.mechanism ? ` · ${c.mechanism}` : ""}
                    {c.claim ? ` — ${c.claim}` : ""}
                    {c.fix ? (
                      <span className="note"> → {c.fix}</span>
                    ) : null}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {review.missed_voices && review.missed_voices.length > 0 && (
            <p className="note">
              被忽略的声音：{review.missed_voices.join("、")}
            </p>
          )}
          {review.skipped_harder_node && (
            <p className="note">更难却被跳过的节点：{review.skipped_harder_node}</p>
          )}
          {review.alternative_thesis && (
            <p className="note">备选命题：{review.alternative_thesis}</p>
          )}
          {review.reverse_route_note && (
            <p className="note">逆走注记：{review.reverse_route_note}</p>
          )}
        </div>
      )}

      {sources.length > 0 && (
        <div className="done-sources">
          <p className="scene-label">出处索引（逐条可核）</p>
          <ul>
            {sources.map((s) => (
              <li key={`${s.dataset}-${s.record_id}`}>
                {datasetLabel(s.dataset)} · <code>{s.record_id}</code>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="export-row">
        <button
          type="button"
          className="btn export"
          onClick={() => exportPdf(doc)}
        >
          导出 PDF
        </button>
        <button
          type="button"
          className="btn export"
          onClick={() => exportEpub(doc)}
        >
          导出 EPUB
        </button>
      </div>

      <div className="btn-row" style={{ justifyContent: "center", marginTop: "1rem" }}>
        <button type="button" className="btn" onClick={onRestart}>
          再策一条
        </button>
      </div>

      <p className="note story-footnote">
        目录给条目，我们给关系。可随时合上书页，不算「未完成」。
      </p>
    </section>
  );
}
