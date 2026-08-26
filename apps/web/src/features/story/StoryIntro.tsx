import { useMemo } from "react";
import type { RouteEnvelope, HongyuanMeta } from "@redtrip/contracts";
import type { StoryView } from "./storyView";
import { NarrativeMap, ROLE_LABEL } from "./NarrativeMap";
import { buildBookDoc, exportPdf, exportEpub, type BookDoc } from "./exportBook";

type Props = {
  envelope: RouteEnvelope;
  storyView: StoryView;
  hongyuan?: HongyuanMeta | null;
  onBegin: () => void;
  onShowMap: () => void;
  onRestart: () => void;
};

function readingLine(h: HongyuanMeta | null | undefined): string {
  if (!h) return "";
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

export function StoryIntro({
  envelope,
  storyView,
  hongyuan,
  onBegin,
  onShowMap,
  onRestart,
}: Props) {
  const q = storyView.quality;
  const hongyuanLine = readingLine(hongyuan);
  const doc: BookDoc = useMemo(
    () => buildBookDoc(envelope, storyView, hongyuan),
    [envelope, storyView, hongyuan],
  );
  // 序章导读：策展自述 / 逻辑线优先，避免与 thesis 重复
  const prelude = [envelope.curator_note, envelope.logic_line].filter(
    (s): s is string => Boolean(s && s !== storyView.thesis),
  );

  return (
    <section className="panel story-intro book-page-flat">
      <p className="note story-kicker">城市记忆策展人 · 可溯源书页</p>
      <h1 className="story-title">{storyView.themeTitle}</h1>
      <p className="lead story-thesis">{storyView.thesis}</p>

      {hongyuanLine && <p className="hongyuan-reading">{hongyuanLine}</p>}

      {hongyuan && (
        <div className="hongyuan-seal-strip" aria-label="红鸢抽签">
          <span className="hongyuan-seal" aria-hidden>
            鸢
          </span>
          <div className="hongyuan-seal-slots">
            {[
              hongyuan.emotion?.label,
              hongyuan.voice_style?.label,
              hongyuan.narrative?.label,
              hongyuan.pacing?.label,
            ]
              .filter(Boolean)
              .map((label) => (
                <span key={label as string} className="hongyuan-slot-chip">
                  {label}
                </span>
              ))}
            {hongyuan.layer3_week ? (
              <span className="hongyuan-slot-chip is-l3">
                L3 · {hongyuan.layer3_week}
              </span>
            ) : null}
          </div>
        </div>
      )}

      {prelude.length > 0 && (
        <div className="story-prelude">
          <p className="scene-label">导读</p>
          {prelude.map((p, i) => (
            <p className="note" key={i}>
              {p}
            </p>
          ))}
        </div>
      )}

      {storyView.cast.length > 0 && (
        <div className="cast-row">
          <span className="scene-label">出场人物</span>
          <div className="cast-chips">
            {storyView.cast.map((e) => (
              <span key={e.id} className="cast-chip static">
                {e.name}
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="story-arc">
        <p className="toc-label">章节脉络</p>
        <NarrativeMap chapters={storyView.chapters} />
      </div>

      <ol className="chapter-list">
        {storyView.chapters.map((c) => (
          <li key={c.id} className="chapter-list-item">
            <span className="chapter-num">{String(c.index).padStart(2, "0")}</span>
            <span className={`role-badge role-${c.narrativeRole.toLowerCase()}`}>
              {ROLE_LABEL[c.narrativeRole]}
            </span>
            <div className="chapter-body">
              <span className="chapter-name">{c.title}</span>
              <span className="chapter-hook">{c.hook}</span>
              {c.relationToPrevious && (
                <span className="chapter-rel">↳ {c.relationToPrevious}</span>
              )}
            </div>
            {c.walkingMinutes > 0 && (
              <span className="chapter-min">{c.walkingMinutes}′</span>
            )}
          </li>
        ))}
      </ol>

      {q && (
        <p className="story-quality">
          证据层 {q.evidence_layers} · 溯源覆盖{" "}
          {(q.coverage_ratio * 100).toFixed(0)}% · 句子对齐{" "}
          {(q.aligned_ratio * 100).toFixed(0)}%
          {storyView.mode === "derived"
            ? " · 简化视图（未含章节结构）"
            : ""}
        </p>
      )}

      <div className="btn-row story-cta">
        <button type="button" className="btn primary" onClick={onBegin}>
          开始这场漫步
        </button>
        <button type="button" className="btn" onClick={onShowMap}>
          看本章在街上的位置
        </button>
        <button type="button" className="btn secondary" onClick={onRestart}>
          重新出题
        </button>
      </div>

      <div className="export-row">
        <button type="button" className="btn export" onClick={() => exportPdf(doc)}>
          导出 PDF
        </button>
        <button type="button" className="btn export" onClick={() => exportEpub(doc)}>
          导出 EPUB
        </button>
      </div>

      <p className="note story-footnote">
        约 {envelope.route.duration_min} 分钟 · 步行估{" "}
        {envelope.route.walk_meters_est} 米 · {envelope.scenario}
      </p>
    </section>
  );
}
