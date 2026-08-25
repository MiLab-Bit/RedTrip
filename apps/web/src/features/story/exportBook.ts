import type {
  RouteEnvelope,
  HongyuanMeta,
  SourceRef,
} from "@redtrip/contracts";
import type { StoryView } from "./storyView";

/* ------------------------------------------------------------------ *
 *  RedTrip 导出引擎（零依赖）
 *  - PDF ：注入打印容器 + window.print()（用户「另存为 PDF」即得书页）
 *  - EPUB：手写 store-only ZIP（含 CRC32）+ EPUB3 结构，Blob 下载
 * ------------------------------------------------------------------ */

export type BookChapter = {
  index: number;
  role: string;
  roleLabel: string;
  title: string;
  hook: string;
  relation: string | null;
  storyTitle: string;
  storyBody: string; // 已清理的散文正文（段落以 \n 分隔）
  scene?: {
    place: string;
    today: string;
    era: string;
    figures: string;
    visual: string;
  };
  sources: { dataset: string; record_id: string }[];
};

export type BookDoc = {
  title: string;
  thesis: string;
  readingLine: string;
  cast: string[];
  prelude: string[];
  chapters: BookChapter[];
  epilogue: string[];
  sourcesIndex: { dataset: string; record_id: string }[];
  meta: { durationMin: number; walkMeters: number; scenario: string };
  review?: {
    warnings: string[];
    concerns: { claim?: string; node?: string; mechanism?: string; fix?: string }[];
    missed_voices: string[];
    alternative_thesis: string;
    reverse_route_note: string;
    skipped_harder_node: string;
  } | null;
};

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function escapeXml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

/** 去除正文里的溯源标记令牌（如 [[fact:...]]），并将换行规范为段落。 */
function cleanBody(raw: string | undefined): string {
  if (!raw) return "";
  return raw
    .replace(/\[\[[^\]]*\]\]/g, "")
    .replace(/\r\n/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function bodyToParagraphs(raw: string | undefined): string[] {
  const cleaned = cleanBody(raw);
  if (!cleaned) return [];
  return cleaned.split(/\n{2,}/).map((p) => p.trim()).filter(Boolean);
}

function datasetLabel(dataset: string): string {
  const map: Record<string, string> = {
    slc_building: "上图书目 · 建筑",
    slc_event: "上图事件",
    slc_person: "上图人物",
    slc_era: "纪年",
    slc_poem: "诗词",
    geoname: "地名志",
    literary: "文学交集",
  };
  return map[dataset] ?? dataset;
}

/** 汇总全书内容：序章 + 各章散文 + 跋 + 出处索引。 */
export function buildBookDoc(
  env: RouteEnvelope,
  view: StoryView,
  hongyuan?: HongyuanMeta | null,
): BookDoc {
  const readingLine = hongyuan
    ? hongyuan.summary ||
      [hongyuan.emotion?.label, hongyuan.narrative?.label, hongyuan.pacing?.label]
        .filter(Boolean)
        .join(" · ")
    : "";

  // 序章导读：拼合策展自述 / 逻辑线 / 美学 / 为何值得去
  const prelude: string[] = [];
  if (env.curator_note) prelude.push(env.curator_note);
  if (env.logic_line && env.logic_line !== env.curator_note)
    prelude.push(env.logic_line);
  if (env.aesthetic) prelude.push(`这一程的读法：${env.aesthetic}。`);
  if (prelude.length === 0 && env.why_visit) prelude.push(env.why_visit);

  const chapters: BookChapter[] = view.chapters.map((c) => {
    const stop = env.route.stops.find((s) => s.order === c.stopId) ?? env.route.stops[0];
    const story = env.blocks.find(
      (b) => b.type === "story_card" && b.stop_order === stop.order,
    );
    const scene = env.blocks.find(
      (b) => b.type === "scene" && b.stop_order === stop.order,
    );
    return {
      index: c.index,
      role: c.narrativeRole,
      roleLabel: roleLabelOf(c.narrativeRole),
      title: c.title,
      hook: c.hook,
      relation: c.relationToPrevious,
      storyTitle: story && story.type === "story_card" ? story.title : "",
      storyBody: cleanBody(
        story && story.type === "story_card" ? story.body : "",
      ),
      scene:
        scene && scene.type === "scene"
          ? {
              place: scene.place ?? "",
              today: scene.today ?? "",
              era: scene.era_desc ?? "",
              figures: scene.figures ?? "",
              visual: scene.visual_note ?? "",
            }
          : undefined,
      sources:
        story && story.type === "story_card"
          ? (story.sources ?? []).map((s: SourceRef) => ({
              dataset: s.dataset,
              record_id: s.record_id,
            }))
          : [],
    };
  });

  // 跋：收束语 + 路线回望
  const epilogue: string[] = [];
  epilogue.push(
    `合上书页前，再走一遍这条线：${view.chapters
      .map((c) => c.title)
      .join(" → ")}。`,
  );
  if (env.why_visit) epilogue.push(env.why_visit);
  epilogue.push(
    "目录给条目，我们给关系。每一处都来自上海图书馆的开放数据，逐条可核——你随时可以合上这页，不算未完成。",
  );

  // 出处索引（去重）
  const seen = new Set<string>();
  const sourcesIndex: { dataset: string; record_id: string }[] = [];
  for (const ch of chapters) {
    for (const s of ch.sources) {
      const key = `${s.dataset}::${s.record_id}`;
      if (!seen.has(key)) {
        seen.add(key);
        sourcesIndex.push(s);
      }
    }
  }
  for (const s of env.sources ?? []) {
    if (!seen.has(`env::${s}`)) {
      seen.add(`env::${s}`);
      sourcesIndex.push({ dataset: "source", record_id: s });
    }
  }

  const cr = env.curator_review;
  const review =
    cr &&
    ((cr.warnings && cr.warnings.length) ||
      (cr.concerns && cr.concerns.length) ||
      (cr.missed_voices && cr.missed_voices.length) ||
      cr.alternative_thesis ||
      cr.reverse_route_note ||
      cr.skipped_harder_node)
      ? {
          warnings: (cr.warnings ?? []).filter(Boolean),
          concerns: (cr.concerns ?? []).map((c) => ({
            claim: c.claim ?? undefined,
            node: c.node ?? undefined,
            mechanism: c.mechanism ?? undefined,
            fix: c.fix ?? undefined,
          })),
          missed_voices: (cr.missed_voices ?? []).filter(Boolean),
          alternative_thesis: cr.alternative_thesis ?? "",
          reverse_route_note: cr.reverse_route_note ?? "",
          skipped_harder_node: cr.skipped_harder_node ?? "",
        }
      : null;

  return {
    title: view.themeTitle || env.theme,
    thesis: view.thesis || env.why_visit || "",
    readingLine,
    cast: view.cast.map((e) => e.name),
    prelude,
    chapters,
    epilogue,
    sourcesIndex,
    review,
    meta: {
      durationMin: env.route.duration_min,
      walkMeters: env.route.walk_meters_est,
      scenario: env.scenario,
    },
  };
}

function roleLabelOf(role: string): string {
  const m: Record<string, string> = {
    Hook: "钩子",
    Anchor: "锚点",
    Contrast: "对照",
    Reveal: "揭显",
    Afterimage: "余像",
    Bridge: "过渡",
  };
  return m[role] ?? role;
}

/* ----------------------------- PDF（打印） ----------------------------- */

function bookHtml(doc: BookDoc): string {
  const chapHtml = doc.chapters
    .map((c) => {
      const paras = c.storyBody
        ? bodyToParagraphs(c.storyBody)
            .map((p) => `<p>${escapeHtml(p)}</p>`)
            .join("")
        : `<p class="note">（本章叙事待生成）</p>`;
      const scene = c.scene
        ? `<div class="scene"><span class="k">舞台</span>${escapeHtml(
            c.scene.place,
          )}　<span class="k">此刻</span>${escapeHtml(c.scene.today)}</div>`
        : "";
      const src = c.sources.length
        ? `<div class="srcs"><span class="k">出处</span>${c.sources
            .map((s) => escapeHtml(datasetLabel(s.dataset)))
            .join("、")}</div>`
        : "";
      return `<section class="chapter">
  <h2>
    <span class="num">${String(c.index).padStart(2, "0")}</span>
    <span class="num-text">
      <span class="role">${escapeHtml(c.roleLabel)}</span>
      <span class="title">${escapeHtml(c.title)}</span>
    </span>
  </h2>
  ${c.hook ? `<p class="hook">${escapeHtml(c.hook)}</p>` : ""}
  ${scene}
  ${paras}
  ${src}
</section>`;
    })
    .join("\n");

  const prelude = doc.prelude.length
    ? `<section class="prelude"><h2>序</h2><span class="ornament-line"></span>${doc.prelude
        .map((p) => `<p>${escapeHtml(p)}</p>`)
        .join("")}</section>`
    : "";
  const epilogue = doc.epilogue.length
    ? `<section class="epilogue"><h2>跋</h2><span class="ornament-line"></span>${doc.epilogue
        .map((p) => `<p>${escapeHtml(p)}</p>`)
        .join("")}</section>`
    : "";
  const cast = doc.cast.length
    ? `<div class="cast"><span class="k">出场人物</span>${doc.cast
        .map(escapeHtml)
        .join("、")}</div>`
    : "";
  const srcIndex = doc.sourcesIndex.length
    ? `<section class="srcindex"><h2>出处索引</h2><span class="ornament-line"></span><ul>${doc.sourcesIndex
        .map(
          (s, i) =>
            `<li><span class="ix">${String(i + 1).padStart(2, "0")}</span><span class="dataset">${escapeHtml(
              datasetLabel(s.dataset),
            )}</span><code>${escapeHtml(s.record_id)}</code></li>`,
        )
        .join("")}</ul></section>`
    : "";

  const review = doc.review
    ? `<section class="review"><h2>策展留白 · 反方策展人</h2><span class="ornament-line"></span>
    <p class="note">以下为对抗性评审留下的未决问题，不构成定论。</p>
    ${
      doc.review.warnings.length
        ? `<p class="k">评审告警</p><ul>${doc.review.warnings
            .map((w) => `<li>${escapeHtml(w)}</li>`)
            .join("")}</ul>`
        : ""
    }
    ${
      doc.review.concerns.length
        ? `<p class="k">反对意见</p><ul>${doc.review.concerns
            .map(
              (c) =>
                `<li><strong>${escapeHtml(c.node || "全路线")}</strong>${
                  c.claim ? ` — ${escapeHtml(c.claim)}` : ""
                }${c.fix ? ` → ${escapeHtml(c.fix)}` : ""}</li>`,
            )
            .join("")}</ul>`
        : ""
    }
    ${
      doc.review.alternative_thesis
        ? `<p class="note">备选命题：${escapeHtml(doc.review.alternative_thesis)}</p>`
        : ""
    }
    </section>`
    : "";

  return `<article class="print-book-inner">
  <header class="book-cover">
    <span class="top-rule" aria-hidden></span>
    <p class="kicker">红鸢 · RedTrip · 城市记忆策展人</p>
    <h1>${escapeHtml(doc.title)}</h1>
    <span class="ornament" aria-hidden><span class="line"></span><span class="dot"></span><span class="line"></span></span>
    ${doc.thesis ? `<p class="thesis">${escapeHtml(doc.thesis)}</p>` : ""}
    ${doc.readingLine ? `<p class="reading">${escapeHtml(doc.readingLine)}</p>` : ""}
    <p class="meta">约 ${doc.meta.durationMin} 分钟 · 步行估 ${doc.meta.walkMeters} 米 · ${escapeHtml(
      doc.meta.scenario,
    )}</p>
    <p class="seal">可　·　溯　·　源</p>
  </header>
  ${prelude}
  ${chapHtml}
  ${epilogue}
  ${cast}
  ${review}
  ${srcIndex}
</article>`;
}

function ensurePrintStyles(): void {
  if (document.getElementById("redtrip-print-style")) return;
  const style = document.createElement("style");
  style.id = "redtrip-print-style";
  style.textContent = `
@media print {
  /* === A4 纸张 + 书籍级留白 === */
  @page { size: A4; margin: 22mm 18mm 18mm 18mm; }
  html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  body.printing > *:not(.print-book) { display: none !important; }
  /* 纯白纸张底（不再用米黄），与屏幕书页通过同一组 design tokens 保持视觉同源 */
  body.printing { background: #ffffff !important; }
  .print-book { display: block !important; padding: 0; }
  .print-book-inner {
    max-width: 100%;
    /* 与屏幕同族：Songti/SC 衬线为主，Georgia 为西文衬线；无衬线仅用于 kicker/meta/印章 */
    font-family: "Noto Serif SC","Songti SC","Source Han Serif SC",Georgia,"Times New Roman",serif;
    color: #1a1410;
    line-height: 2.0;
    font-size: 11pt;
  }

  /* === 封面：纯白纸 + 细线 + 菱形装饰 + 印章 === */
  .print-book-inner .book-cover {
    text-align: center;
    padding: 38mm 10mm 28mm;
    break-after: page; page-break-after: always;
    break-inside: avoid;
  }
  .print-book-inner .book-cover .top-rule {
    border-top: 0.5pt solid #b0925e;
    margin: 0 auto 22mm;
    width: 56mm;
  }
  .print-book-inner .book-cover .kicker {
    font-family: "PingFang SC","Helvetica Neue",sans-serif;
    font-size: 9pt; letter-spacing: 0.22em; color: #8a7a5e;
    text-transform: uppercase;
    margin: 0 0 26mm;
  }
  .print-book-inner .book-cover h1 {
    font-size: 30pt; letter-spacing: 0.14em;
    margin: 0 0 16mm; color: #1a1410; font-weight: 600;
    line-height: 1.35;
  }
  .print-book-inner .book-cover .ornament {
    display: flex; align-items: center; justify-content: center;
    gap: 8pt; margin: 10mm auto 14mm; width: 60mm;
  }
  .print-book-inner .book-cover .ornament .line { flex: 1; height: 0.5pt; background: #b0925e; }
  .print-book-inner .book-cover .ornament .dot { width: 4pt; height: 4pt; background: #b0925e; transform: rotate(45deg); }
  .print-book-inner .book-cover .thesis {
    font-size: 12.5pt; color: #4a3f2e; font-style: italic;
    margin: 0 16mm 14mm; line-height: 2.05;
  }
  .print-book-inner .book-cover .reading {
    font-family: "Noto Serif SC",Georgia,serif;
    font-size: 10.5pt; color: #4a3f2e;
    margin: 4mm 14mm 18mm; line-height: 2.0;
  }
  .print-book-inner .book-cover .meta {
    font-family: "PingFang SC","Helvetica Neue",sans-serif;
    font-size: 9pt; letter-spacing: 0.12em; color: #8a7a5e;
    margin: 18mm 0 0;
  }
  .print-book-inner .book-cover .seal {
    display: inline-block; margin-top: 14mm;
    padding: 5pt 14pt;
    border: 1pt solid #b0925e;
    color: #b0925e;
    font-family: "Noto Serif SC",Georgia,serif;
    font-size: 10pt; letter-spacing: 0.3em; font-weight: 600;
  }

  /* === 扉页 / 跋（序））：） === */
  .print-book-inner .prelude,
  .print-book-inner .epilogue {
    break-before: page; page-break-before: always;
    padding: 32mm 14mm 0;
    text-align: center;
  }
  .print-book-inner .prelude h2,
  .print-book-inner .epilogue h2 {
    font-family: "PingFang SC","Helvetica Neue",sans-serif;
    font-size: 14pt; letter-spacing: 0.4em;
    text-align: center; color: #1a1410;
    margin: 0 0 12mm; border: none; font-weight: 600;
  }
  .print-book-inner .prelude .ornament-line,
  .print-book-inner .epilogue .ornament-line {
    display: block; width: 28mm; height: 1.5pt; background: #b0925e;
    margin: 0 auto 16mm;
  }
  .print-book-inner .prelude p,
  .print-book-inner .epilogue p {
    text-indent: 2em; text-align: justify;
    font-size: 11pt; color: #1a1410; line-height: 2.1;
    margin: 0 0 6pt;
  }

  /* === 章节：超大字章号 + 角色标签 + 引言 + 场景格 + 正文 + 出处条 === */
  .print-book-inner .chapter {
    break-before: page; page-break-before: always;
    padding: 4mm 0 0;
  }
  .print-book-inner .chapter h2 {
    display: flex; align-items: flex-start; gap: 14pt;
    margin: 0 0 12mm; padding: 0; border: none;
  }
  .print-book-inner .chapter .num {
    font-family: Georgia,"Times New Roman",serif;
    font-size: 40pt; color: #b0925e; line-height: 1; font-weight: 400;
    flex-shrink: 0;
  }
  .print-book-inner .chapter .num-text {
    display: flex; flex-direction: column; gap: 6pt;
    padding-top: 4pt;
  }
  .print-book-inner .chapter .role {
    font-family: "PingFang SC","Helvetica Neue",sans-serif;
    font-size: 8.5pt; letter-spacing: 0.22em;
    color: #8a7a5e; text-transform: uppercase;
  }
  .print-book-inner .chapter .title {
    font-family: "Noto Serif SC",Georgia,serif;
    font-size: 21pt; color: #1a1410; font-weight: 600;
    line-height: 1.35;
  }
  .print-book-inner .chapter .hook {
    font-style: italic; color: #4a3f2e; font-size: 11.5pt;
    margin: 0 0 8mm; padding: 0 0 0 8mm;
    border-left: 3pt solid #b0925e;
  }
  .print-book-inner .chapter .scene {
    font-family: "PingFang SC","Helvetica Neue",sans-serif;
    font-size: 9pt; color: #8a7a5e;
    margin: 0 0 8mm; padding: 4pt 0 4pt 8mm;
    border-left: 1pt solid #c9a45c;
  }
  .print-book-inner .chapter .scene .k {
    display: inline-block; min-width: 3.5em;
    color: #b0925e; letter-spacing: 0.12em;
  }
  .print-book-inner .chapter p {
    text-indent: 2em; text-align: justify;
    font-size: 11pt; line-height: 2.05;
    color: #1a1410; margin: 0 0 4pt;
  }
  .print-book-inner .chapter .srcs {
    font-family: "PingFang SC","Helvetica Neue",sans-serif;
    font-size: 9pt; color: #8a7a5e;
    margin: 8mm 0 0; padding: 4pt 0 4pt 8mm;
    border-left: 3pt solid #b0925e;
  }
  .print-book-inner .chapter .srcs .k {
    color: #b0925e; letter-spacing: 0.12em; margin-right: 0.6em;
  }

  /* === 出场人物条（独立位置、放在章节之前） === */
  .print-book-inner .cast {
    margin: 0 0 12mm; padding: 0;
    font-family: "PingFang SC","Helvetica Neue",sans-serif;
    font-size: 9.5pt; color: #8a7a5e;
  }
  .print-book-inner .cast .k {
    color: #b0925e; letter-spacing: 0.18em;
    margin-right: 0.8em;
  }

  /* === 出处索引：独立页 + 编号列 === */
  .print-book-inner .srcindex {
    break-before: page; page-break-before: always;
    padding: 32mm 0 0;
  }
  .print-book-inner .srcindex h2 {
    font-family: "PingFang SC","Helvetica Neue",sans-serif;
    font-size: 14pt; letter-spacing: 0.4em;
    text-align: center; color: #1a1410;
    margin: 0 0 12mm; border: none; font-weight: 600;
  }
  .print-book-inner .srcindex .ornament-line {
    display: block; width: 28mm; height: 1.5pt; background: #b0925e;
    margin: 0 auto 14mm;
  }
  .print-book-inner .srcindex ul {
    list-style: none; padding: 0; margin: 0;
  }
  .print-book-inner .srcindex li {
    display: flex; align-items: baseline; gap: 10pt;
    padding: 4pt 0;
    border-bottom: 0.5pt dotted #c9a45c;
    font-size: 10pt; color: #4a3f2e;
  }
  .print-book-inner .srcindex li .ix {
    font-family: Georgia,serif; color: #b0925e;
    flex-shrink: 0; width: 18pt;
  }
  .print-book-inner .srcindex li .dataset { flex: 1; }
  .print-book-inner .srcindex li code {
    font-family: "SF Mono","Menlo",monospace;
    font-size: 8.5pt; color: #8a7a5e;
  }

  /* === 书籍级排版细节（孤行、避免孤寡） === */
  .print-book-inner h1, .print-book-inner h2 {
    break-after: avoid-page; page-break-after: avoid;
    break-inside: avoid;
  }
  .print-book-inner .scene,
  .print-book-inner .cast,
  .print-book-inner .srcs,
  .print-book-inner .hook {
    break-inside: avoid; page-break-inside: avoid;
  }
  .print-book-inner p { orphans: 3; widows: 3; }
}
`;
  document.head.appendChild(style);
}

export function exportPdf(doc: BookDoc): void {
  ensurePrintStyles();
  const host = document.createElement("div");
  host.className = "print-book";
  host.style.display = "none";
  host.innerHTML = bookHtml(doc);
  document.body.appendChild(host);
  document.body.classList.add("printing");

  /*
   * 清理时序说明（原实现有一个真实缺陷）：
   * 旧代码用 setTimeout(cleanup, 10000) 兜底，但用户在系统打印对话框里
   * 挑打印机、翻预览、选「另存为 PDF」的路径，超过 10s 极其常见。
   * 一旦超时先触发，body.printing 与内容节点会在打印进行中被摘掉，
   * 导出结果直接变成空白页或整个 SPA 界面。
   *
   * 现在三重判定，任一可靠信号到达才清理：
   *   1) afterprint 事件（主路径，主流浏览器都会触发）；
   *   2) matchMedia("print") 由 true 转 false（Safari 等的补充信号）；
   *   3) 长兜底轮询——只在确认「已不处于打印态」时才动手，
   *      否则继续等，绝不在打印中途抽走内容。
   */
  const mql =
    typeof window.matchMedia === "function" ? window.matchMedia("print") : null;
  let finished = false;
  let fallbackTimer: number | undefined;

  const detach = () => {
    window.removeEventListener("afterprint", cleanup);
    if (mql && typeof mql.removeEventListener === "function") {
      mql.removeEventListener("change", onMediaChange);
    }
  };

  function cleanup(): void {
    if (finished) return;
    // 仍在打印/预览态：不动手，等后续信号或下一轮兜底。
    if (mql?.matches) return;
    finished = true;
    if (fallbackTimer !== undefined) window.clearTimeout(fallbackTimer);
    document.body.classList.remove("printing");
    if (host.parentNode) host.parentNode.removeChild(host);
    detach();
  }

  function onMediaChange(e: MediaQueryListEvent): void {
    if (!e.matches) cleanup();
  }

  window.addEventListener("afterprint", cleanup);
  if (mql && typeof mql.addEventListener === "function") {
    mql.addEventListener("change", onMediaChange);
  }

  // 给样式一帧生效时间再打印
  window.requestAnimationFrame(() => window.print());

  // 兜底轮询：首次 60s 后开始检查，若仍在打印态则每 5s 复查，不硬拆。
  const tick = () => {
    if (finished) return;
    if (mql?.matches) {
      fallbackTimer = window.setTimeout(tick, 5000);
      return;
    }
    cleanup();
  };
  fallbackTimer = window.setTimeout(tick, 60000);
}

/* ----------------------------- EPUB（ZIP） ----------------------------- */

const CRC_TABLE = (() => {
  const t = new Uint32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) {
      c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    }
    t[n] = c >>> 0;
  }
  return t;
})();

function crc32(bytes: Uint8Array): number {
  let c = 0xffffffff;
  for (let i = 0; i < bytes.length; i++) {
    c = CRC_TABLE[(c ^ bytes[i]) & 0xff] ^ (c >>> 8);
  }
  return (c ^ 0xffffffff) >>> 0;
}

function strToU8(s: string): Uint8Array {
  return new TextEncoder().encode(s);
}

/**
 * 生成 store-only（无压缩）ZIP。
 *
 * 返回类型显式写成 `Uint8Array<ArrayBuffer>`：TS 5.7 起 TypedArray 对底层 buffer
 * 泛型化，默认推断成 `Uint8Array<ArrayBufferLike>`，而 `BlobPart` 只接受
 * `ArrayBufferView<ArrayBuffer>`（ArrayBufferLike 包含 SharedArrayBuffer）。
 * 此处 out 由 `new Uint8Array(total)` 创建，底层必然是独占的 ArrayBuffer，
 * 收窄类型即可直接喂给 `new Blob([...])`，无需多拷一份。
 */
function zipStore(
  files: { name: string; data: Uint8Array }[],
): Uint8Array<ArrayBuffer> {
  const enc = new TextEncoder();
  const locals: Uint8Array[] = [];
  const centrals: Uint8Array[] = [];
  let offset = 0;

  for (const f of files) {
    const nameBytes = enc.encode(f.name);
    const crc = crc32(f.data);
    const size = f.data.length;

    const local = new Uint8Array(30 + nameBytes.length + size);
    const lv = new DataView(local.buffer);
    lv.setUint32(0, 0x04034b50, true);
    lv.setUint16(4, 20, true); // version needed
    lv.setUint16(6, 0x0800, true); // UTF-8 flag
    lv.setUint16(8, 0, true); // method = store
    lv.setUint16(10, 0, true); // mod time
    lv.setUint16(12, 0, true); // mod date
    lv.setUint32(14, crc, true);
    lv.setUint32(18, size, true); // compressed
    lv.setUint32(22, size, true); // uncompressed
    lv.setUint16(26, nameBytes.length, true);
    lv.setUint16(28, 0, true); // extra len
    local.set(nameBytes, 30);
    local.set(f.data, 30 + nameBytes.length);

    const central = new Uint8Array(46 + nameBytes.length);
    const cv = new DataView(central.buffer);
    cv.setUint32(0, 0x02014b50, true);
    cv.setUint16(4, 20, true); // version made by
    cv.setUint16(6, 20, true); // version needed
    cv.setUint16(8, 0x0800, true); // UTF-8 flag
    cv.setUint16(10, 0, true); // method
    cv.setUint16(12, 0, true); // mod time
    cv.setUint16(14, 0, true); // mod date
    cv.setUint32(16, crc, true);
    cv.setUint32(20, size, true);
    cv.setUint32(24, size, true);
    cv.setUint16(28, nameBytes.length, true);
    cv.setUint16(30, 0, true); // extra
    cv.setUint16(32, 0, true); // comment
    cv.setUint16(34, 0, true); // disk
    cv.setUint16(36, 0, true); // internal attr
    cv.setUint32(38, 0, true); // external attr
    cv.setUint32(42, offset, true); // local header offset
    central.set(nameBytes, 46);

    locals.push(local);
    centrals.push(central);
    offset += local.length;
  }

  const centralSize = centrals.reduce((s, c) => s + c.length, 0);
  const total = locals.reduce((s, l) => s + l.length, 0) + centralSize + 22;
  const out = new Uint8Array(total);
  let pos = 0;
  for (const l of locals) {
    out.set(l, pos);
    pos += l.length;
  }
  for (const c of centrals) {
    out.set(c, pos);
    pos += c.length;
  }
  const end = new DataView(out.buffer, out.byteOffset + pos, 22);
  end.setUint32(0, 0x06054b50, true);
  end.setUint16(4, 0, true);
  end.setUint16(6, 0, true);
  end.setUint16(8, files.length, true);
  end.setUint16(10, files.length, true);
  end.setUint32(12, centralSize, true);
  end.setUint32(16, offset, true);
  end.setUint16(20, 0, true);
  return out;
}

function epubChapterHtml(c: BookChapter): string {
  const paras = c.storyBody
    ? bodyToParagraphs(c.storyBody)
        .map((p) => `<p>${escapeXml(p)}</p>`)
        .join("\n")
    : `<p>（本章叙事待生成）</p>`;
  const scene = c.scene
    ? `<p class="scene"><strong>舞台</strong> ${escapeXml(
        c.scene.place,
      )}　<strong>此刻</strong> ${escapeXml(c.scene.today)}</p>`
    : "";
  const src = c.sources.length
    ? `<p class="src"><strong>出处</strong> ${c.sources
        .map((s) => escapeXml(datasetLabel(s.dataset)))
        .join("、")}</p>`
    : "";
  return `<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="zh">
<head><meta charset="utf-8"/><title>${escapeXml(c.title)}</title></head>
<body>
<h2><span class="num">${String(c.index).padStart(2, "0")}</span> ${escapeXml(
    c.roleLabel,
  )} · ${escapeXml(c.title)}</h2>
${c.hook ? `<p class="hook">${escapeXml(c.hook)}</p>` : ""}
${scene}
${paras}
${src}
</body></html>`;
}

/** 由标题派生稳定且合法的 UUID（同一本书每次导出一致，epubcheck 友好）。 */
function stableBookUuid(title: string): string {
  const enc = new TextEncoder();
  const bytes = enc.encode(title || "redtrip");
  const mix = (h: number, b: number) => (Math.imul(h ^ b, 0x01000193) >>> 0);
  let h1 = 0x811c9dc5, h2 = 0x9b5cffe5, h3 = 0x62b82175, h4 = 0x07bb0142;
  for (const b of bytes) {
    h1 = mix(h1, b);
    h2 = mix(h2, b << 1);
    h3 = mix(h3, b << 2);
    h4 = mix(h4, b << 3);
  }
  const hex = (n: number) => (n >>> 0).toString(16).padStart(8, "0");
  const raw = hex(h1) + hex(h2) + hex(h3) + hex(h4);
  // 规整为 RFC4122 v4 形状（确定性）
  return `${raw.slice(0, 8)}-${raw.slice(8, 12)}-4${raw.slice(13, 16)}-8${raw.slice(
    17,
    20,
  )}-${raw.slice(20, 32)}`;
}

export function exportEpub(doc: BookDoc): void {
  const safeTitle = doc.title.replace(/[\\/:*?"<>|]/g, "_").slice(0, 60) || "RedTrip";
  const files: { name: string; data: Uint8Array }[] = [];

  // mimetype 必须第一个且 store（无压缩）
  files.push({
    name: "mimetype",
    data: strToU8("application/epub+zip"),
  });

  files.push({
    name: "META-INF/container.xml",
    data: strToU8(`<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>`),
  });

  const styleCss = `body{font-family:"Songti SC","Noto Serif SC",serif;line-height:1.9;margin:1.2em;color:#1a1410}
h1{font-size:1.6em;text-align:center}h2{font-size:1.2em;border-bottom:1px solid #d8cbb6;padding-bottom:.3em}
.hook{color:#6b5a36;font-style:italic}.scene,.src,.cast{font-size:.85em;color:#7a6c52}
.num{color:#b0925e;margin-right:.4em}.role{font-size:.7em;background:#efe6d4;padding:.1em .5em;border-radius:1em;margin-right:.4em;color:#6b5a36}`;

  const manifestItems: string[] = [
    `<item id="style" href="style.css" media-type="text/css"/>`,
  ];
  const spineItems: string[] = [];
  const navPoints: string[] = [];

  const chapterXhtml: string[] = [];

  // 序
  const preludeXhtml = `<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="zh">
<head><meta charset="utf-8"/><title>序</title></head>
<body><h2>序</h2>${doc.prelude
    .map((p) => `<p>${escapeXml(p)}</p>`)
    .join("")}</body></html>`;
  chapterXhtml.push(preludeXhtml);
  manifestItems.push(`<item id="prelude" href="prelude.xhtml" media-type="application/xhtml+xml"/>`);
  spineItems.push(`<itemref idref="prelude"/>`);
  navPoints.push(`<li><a href="prelude.xhtml">序</a></li>`);

  doc.chapters.forEach((c, i) => {
    const fn = `chap-${String(c.index).padStart(2, "0")}.xhtml`;
    chapterXhtml.push(epubChapterHtml(c));
    const id = `chap-${i + 1}`;
    manifestItems.push(`<item id="${id}" href="${fn}" media-type="application/xhtml+xml"/>`);
    spineItems.push(`<itemref idref="${id}"/>`);
    navPoints.push(`<li><a href="${fn}">${String(c.index).padStart(2, "0")} ${escapeXml(c.title)}</a></li>`);
  });

  // 跋
  const epilogueXhtml = `<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="zh">
<head><meta charset="utf-8"/><title>跋</title></head>
<body><h2>跋</h2>${doc.epilogue
    .map((p) => `<p>${escapeXml(p)}</p>`)
    .join("")}${
    doc.cast.length
      ? `<p class="cast"><strong>出场人物</strong> ${doc.cast
          .map(escapeXml)
          .join("、")}</p>`
      : ""
  }${
    doc.sourcesIndex.length
      ? `<h2>出处索引</h2><ul>${doc.sourcesIndex
          .map(
            (s) =>
              `<li>${escapeXml(datasetLabel(s.dataset))} · ${escapeXml(s.record_id)}</li>`,
          )
          .join("")}</ul>`
      : ""
  }</body></html>`;
  chapterXhtml.push(epilogueXhtml);
  manifestItems.push(`<item id="epilogue" href="epilogue.xhtml" media-type="application/xhtml+xml"/>`);
  spineItems.push(`<itemref idref="epilogue"/>`);
  navPoints.push(`<li><a href="epilogue.xhtml">跋</a></li>`);

  chapterXhtml.forEach((x, i) => {
    const name = i === 0 ? "prelude.xhtml" : i === chapterXhtml.length - 1 ? "epilogue.xhtml" : `chap-${String(i).padStart(2, "0")}.xhtml`;
    files.push({ name: `OEBPS/${name}`, data: strToU8(x) });
  });
  files.push({ name: "OEBPS/style.css", data: strToU8(styleCss) });

  const opf = `<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="bookid">urn:uuid:${stableBookUuid(doc.title)}</dc:identifier>
    <dc:title>${escapeXml(doc.title)}</dc:title>
    <dc:creator>RedTrip 城市记忆策展人</dc:creator>
    <dc:language>zh</dc:language>
    <meta property="dcterms:modified">${new Date().toISOString().replace(/\.\d+Z$/, "Z")}</meta>
  </metadata>
  <manifest>
    ${manifestItems.join("\n    ")}
    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
  </manifest>
  <spine>
    ${spineItems.join("\n    ")}
  </spine>
</package>`;
  files.push({ name: "OEBPS/content.opf", data: strToU8(opf) });

  const nav = `<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="zh">
<head><meta charset="utf-8"/><title>目录</title></head>
<body>
<nav epub:type="toc" id="toc">
  <h1>${escapeXml(doc.title)} · 目录</h1>
  <ol>${navPoints.join("")}</ol>
</nav>
</body></html>`;
  files.push({ name: "OEBPS/nav.xhtml", data: strToU8(nav) });

  const blob = new Blob([zipStore(files)], {
    type: "application/epub+zip",
  });
  downloadBlob(blob, `${safeTitle}.epub`);
}

/* ------------------------------- 工具 ------------------------------- */

function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  window.setTimeout(() => URL.revokeObjectURL(url), 4000);
}
