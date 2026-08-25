import { useState, useMemo } from "react";
import type { RouteEnvelope, SourceRef } from "@redtrip/contracts";
import { StopPanel } from "./StopPanel";
import {
  chapterFacts,
  chapterStop,
  type StoryView,
} from "../story/storyView";
import { NarrativeMap, ROLE_LABEL } from "../story/NarrativeMap";
import {
  shortRecordId,
  kindLabel,
  datasetLabel,
  isClassicalSource,
  cbdbRecordUrl,
} from "./sourceLabels";
import { classicalVerificationRate } from "./ClassicalLayer";
import { buildBookDoc, exportPdf, exportEpub, type BookDoc } from "../story/exportBook";

type Props = {
  envelope: RouteEnvelope;
  storyView: StoryView;
  currentChapter: number;
  source: SourceRef | null;
  onOpenSource: (source: SourceRef) => void;
  onCloseSource: () => void;
  onOpenChapter: (index: number) => void;
  onPrevChapter: () => void;
  onNextChapter: () => void;
  onShowMap: () => void;
  onBackIntro: () => void;
  onFinish: () => void;
};

/**
 * 可行走的城市故事阅读器。
 * 顶部：叙事地图（章节聚焦）。左侧：章节轨。中部：当前章节叙事卡（逐句可溯源）。
 * 右侧：证据抽屉（本章 evidenceIds → 事实 + 人物）。地图降级为「看全图」子视图。
 */
export function WalkStage({
  envelope,
  storyView,
  currentChapter,
  source,
  onOpenSource,
  onCloseSource,
  onOpenChapter,
  onPrevChapter,
  onNextChapter,
  onShowMap,
  onBackIntro,
  onFinish,
}: Props) {
  const chapter =
    storyView.chapters[currentChapter - 1] ?? storyView.chapters[0];
  const stop = chapter ? chapterStop(envelope, chapter) : envelope.route.stops[0];
  const facts = chapter ? chapterFacts(storyView, chapter) : [];
  const castEntities = chapter
    ? storyView.cast.filter(
        (e) => chapter.castRefs.includes(e.id) || chapter.castRefs.includes(e.name),
      )
    : [];
  const isLast = currentChapter >= storyView.chapters.length;
  const [drawerOpen, setDrawerOpen] = useState(true);
  const doc: BookDoc = useMemo(
    () => buildBookDoc(envelope, storyView, null),
    [envelope, storyView],
  );

  // 典籍溯源分组：本章证据中来自 CBDB 的，单独前置展示
  const classicalFactsHere = facts.filter(
    (f) => f.layer === "classical" || isClassicalSource(f.source_dataset),
  );
  const otherFacts = facts.filter(
    (f) => !(f.layer === "classical" || isClassicalSource(f.source_dataset)),
  );
  const verification = useMemo(
    () => classicalVerificationRate(envelope),
    [envelope],
  );

  return (
    <div className="walk-stage story-reader">
      <div className="reader-map-strip">
        <NarrativeMap
          chapters={storyView.chapters}
          currentIndex={currentChapter}
          onOpenChapter={onOpenChapter}
          showPopover={false}
        />
      </div>

      <div className="reader-body">
        <aside className="reader-rail">
          <p className="toc-label">章节</p>
          <ol className="reader-rail-list">
            {storyView.chapters.map((c) => (
              <li key={c.id}>
                <button
                  type="button"
                  className={`reader-rail-item${
                    c.index === currentChapter ? " is-active" : ""
                  }`}
                  onClick={() => onOpenChapter(c.index)}
                >
                  <span className="reader-rail-num">
                    {String(c.index).padStart(2, "0")}
                  </span>
                  <span className={`role-badge role-${c.narrativeRole.toLowerCase()}`}>
                    {ROLE_LABEL[c.narrativeRole]}
                  </span>
                  <span className="reader-rail-name">{c.title}</span>
                </button>
              </li>
            ))}
          </ol>
          <button type="button" className="toc-action" onClick={onBackIntro}>
            ← 回到序章
          </button>
        </aside>

        <div className="reader-main book-spread">
          <div className="walk-col walk-col-story book-page book-page-left">
            {chapter && (
              <header className="chapter-head">
                <div className="chapter-head-top">
                  <span className="chapter-num">
                    {String(chapter.index).padStart(2, "0")}
                  </span>
                  <span className={`role-badge role-${chapter.narrativeRole.toLowerCase()}`}>
                    {ROLE_LABEL[chapter.narrativeRole]}
                  </span>
                  <h2>{chapter.title}</h2>
                </div>
                <p className="chapter-hook">{chapter.hook}</p>
                {chapter.relationToPrevious && (
                  <p className="chapter-rel">
                    ↳ 上一段落：{chapter.relationToPrevious}
                  </p>
                )}
              </header>
            )}
            <StopPanel
              envelope={envelope}
              stop={stop}
              source={source}
              onOpenSource={onOpenSource}
              onCloseSource={onCloseSource}
              layout="split"
            />
          </div>

          <div className="book-binding" aria-hidden />

          <div className="walk-col walk-col-evidence book-page book-page-right">
            <div className="evidence-head">
              <h3>本章证据</h3>
              <button
                type="button"
                className="evidence-toggle"
                onClick={() => setDrawerOpen((v) => !v)}
              >
                {drawerOpen
                  ? "收起"
                  : `展开 (${facts.length + castEntities.length})`}
              </button>
            </div>
            {drawerOpen && (
              <div className="evidence-scroll">
                {facts.length === 0 && (
                  <p className="note">
                    本章未单独标注证据清单；叙事正文的句末标记仍可逐句溯源。
                  </p>
                )}

                {classicalFactsHere.length > 0 && (
                  <div className="evidence-group evidence-group-classical">
                    <p className="evidence-group-label">
                      <span className="classical-badge small">典</span>
                      典籍溯源
                      <span className="evidence-group-count">
                        {classicalFactsHere.length}
                      </span>
                    </p>
                    {classicalFactsHere.map((f) => {
                      const cbdbUrl = cbdbRecordUrl(f.fact_uri);
                      return (
                        <button
                          type="button"
                          key={f.fact_uri}
                          className="evidence-item evidence-item-classical"
                          onClick={() =>
                            onOpenSource({
                              dataset: f.source_dataset,
                              record_id: f.fact_uri,
                              excerpt: f.assertion,
                            })
                          }
                        >
                          <span className={`layer-badge layer-${f.layer}`}>
                            {kindLabel(f.layer)}
                          </span>
                          <span className="evidence-label">{f.label}</span>
                          <span className="evidence-assertion">{f.assertion}</span>
                          <span className="evidence-record">
                            <code title={f.fact_uri}>{shortRecordId(f.fact_uri)}</code>
                            {cbdbUrl && (
                              <a
                                className="evidence-cbdb-link"
                                href={cbdbUrl}
                                target="_blank"
                                rel="noreferrer"
                                onClick={(e) => e.stopPropagation()}
                                title="在哈佛 CBDB 原库回查"
                              >
                                原库 ↗
                              </a>
                            )}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                )}

                {otherFacts.length > 0 && (
                  <div className="evidence-group">
                    {classicalFactsHere.length > 0 && (
                      <p className="evidence-group-label">其他证据</p>
                    )}
                    {otherFacts.map((f) => (
                      <button
                        type="button"
                        key={f.fact_uri}
                        className="evidence-item"
                        onClick={() =>
                          onOpenSource({
                            dataset: f.source_dataset,
                            record_id: f.fact_uri,
                            excerpt: f.assertion,
                          })
                        }
                      >
                        <span className={`layer-badge layer-${f.layer}`}>
                          {kindLabel(f.layer)}
                        </span>
                        <span className="evidence-label">{f.label}</span>
                        <span className="evidence-assertion">{f.assertion}</span>
                        <span className="evidence-record">
                          <code title={f.fact_uri}>{shortRecordId(f.fact_uri)}</code>
                        </span>
                      </button>
                    ))}
                  </div>
                )}

                {castEntities.length > 0 && (
                  <div className="evidence-cast">
                    <p className="scene-label">本章人物</p>
                    <div className="cast-chips">
                      {castEntities.map((e) => (
                        <span key={e.id} className="cast-chip static">
                          {e.name}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
            <p className="note reader-footnote">
              证据来自上海图书馆开放数据 · 逐条可核
              {verification.total > 0 && (
                <span className="reader-footnote-verify">
                  {" · "}
                  典籍核验 {verification.aligned}/{verification.total}（
                  {Math.round(verification.rate * 100)}%）
                </span>
              )}
            </p>
          </div>
        </div>
      </div>

      <nav className="walk-nav toc-actions" aria-label="章节翻页">
        <button type="button" className="toc-action" onClick={onBackIntro}>
          回序章
        </button>
        <span className="toc-action-sep" aria-hidden>
          ·
        </span>
        <button
          type="button"
          className="toc-action"
          onClick={onPrevChapter}
          disabled={currentChapter <= 1}
        >
          上一章
        </button>
        <span className="toc-action-sep" aria-hidden>
          ·
        </span>
        {!isLast ? (
          <button type="button" className="toc-action primary" onClick={onNextChapter}>
            下一章
          </button>
        ) : (
          <button type="button" className="toc-action primary" onClick={onFinish}>
            收尾
          </button>
        )}
        <span className="toc-action-sep" aria-hidden>
          ·
        </span>
        <button type="button" className="toc-action" onClick={onShowMap}>
          看全图
        </button>
        <span className="toc-action-sep" aria-hidden>
          ·
        </span>
        <span className="reader-export">
          <button type="button" className="btn export" onClick={() => exportPdf(doc)}>
            PDF
          </button>
          <button type="button" className="btn export" onClick={() => exportEpub(doc)}>
            EPUB
          </button>
        </span>
        <span className="toc-action-sep" aria-hidden>
          ·
        </span>
        <button type="button" className="toc-action" onClick={onFinish}>
          就此结束
        </button>
      </nav>
    </div>
  );
}
