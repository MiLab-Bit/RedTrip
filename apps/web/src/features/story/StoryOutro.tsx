import { useMemo } from "react";
import type { RouteEnvelope, HongyuanMeta } from "@redtrip/contracts";
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
