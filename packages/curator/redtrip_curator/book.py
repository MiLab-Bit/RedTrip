"""RedTrip 书籍化渲染器：纯函数，零 token，无副作用。

把内容管线产出的「溯源叙事」envelope 渲染成书籍形态（导览手册）：
- 封面
- 路线规划页（行程表：站序 / 站名 / 停留时长 / 开放与可入内 / 通往下一站）
- 目录（table of contents）
- 序 + 各章（风景与历史 / 人物 / 游玩设计）+ 跋
- 脚注 / 出处索引（colophon）
- 打印友好的单页 HTML（render_book）
- 书籍化 P4 导出：MDX/Markdown（render_book_markdown）、EPUB（render_book_epub_bytes /
  write_epub，stdlib 零依赖、可拆卷）、PDF（render_book_pdf，best-effort wkhtmltopdf，
  否则沿用 render_book 的 @page A4 样式走浏览器打印）

设计约束（架构红线）：
1. 不调用 LLM，不生成新叙事；只把已有 envelope 做确定性转换。

设计约束（架构红线）：
1. 不调用 LLM，不生成新叙事；只把已有 envelope 做确定性转换。
2. 优先消费 `curated_story` 契约；旧 envelope 回落到 `theme` / `blocks`。
3. 章节正文来自 `blocks` 中 type=story_card 的条目，与 `curated_story.chapters` 按 stopId/stop_order 对齐。
4. 场景信息来自 `blocks` 中 type=scene 的条目。
"""
from __future__ import annotations

import html
import io
import logging
import shutil
import subprocess
import uuid
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("redtrip.book")

_ROLE_LABEL: dict[str, str] = {
    "Hook": "引子",
    "Anchor": "锚点",
    "Contrast": "对照",
    "Reveal": "揭显",
    "Afterimage": "余像",
    "Bridge": "过渡",
}

_DATASET_LABEL: dict[str, str] = {
    "geonames_corpus": "地名志",
    "building_detail": "馆藏建筑",
    "road_corpus": "路名志",
    "literary_corpus": "文学交集",
    "curated.landmark-facts": "历史风貌区词库",
    "amap": "高德 POI",
    "slc": "上海图书馆",
    "slc_building": "上图书目 · 建筑",
    "slc_event": "上图事件",
    "slc_person": "上图人物",
    "slc_era": "纪年",
    "slc_poem": "诗词",
    "geoname": "地名志",
    "literary": "文学交集",
    "amap_poi": "高德 POI",
    "source": "外部来源",
}


@dataclass
class BookSource:
    dataset: str
    record_id: str


@dataclass
class BookChapter:
    index: int
    role: str
    role_label: str
    title: str
    hook: str
    relation: str | None
    body_paragraphs: list[str] = field(default_factory=list)
    scene: dict[str, str] | None = None
    sources: list[BookSource] = field(default_factory=list)
    walking_minutes: int = 0
    essay_title: str = ""
    essay_paragraphs: list[str] = field(default_factory=list)


@dataclass
class BookDoc:
    title: str
    thesis: str
    reading_line: str
    cast: list[str]
    prelude: list[str]
    chapters: list[BookChapter]
    epilogue: list[str]
    sources_index: list[BookSource]
    meta: dict[str, Any] = field(default_factory=dict)
    route_plan: dict[str, Any] = field(default_factory=dict)
    review: dict[str, Any] = field(default_factory=dict)


def _label(dataset: str) -> str:
    return _DATASET_LABEL.get(dataset, dataset)


def _clean_body(raw: str) -> str:
    if not raw:
        return ""
    return (
        raw.replace("[[", "").replace("]]", "")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .strip()
    )


def _to_paragraphs(raw: str) -> list[str]:
    cleaned = _clean_body(raw)
    if not cleaned:
        return []
    return [p.strip() for p in cleaned.split("\n\n") if p.strip()]


def _first(obj: Any, *keys: str) -> Any:
    for k in keys:
        if isinstance(obj, dict) and k in obj:
            return obj[k]
    return None


def _build_book_doc(envelope: dict[str, Any]) -> BookDoc:
    """从 envelope 构建结构化 BookDoc（不渲染 HTML）。"""
    curated = envelope.get("curated_story") or {}
    theme = curated.get("theme") or envelope.get("theme_artifact") or {}
    route = envelope.get("route") or {}
    blocks = envelope.get("blocks") or []

    title = (
        theme.get("title")
        or envelope.get("theme")
        or "未命名路线"
    )
    thesis = (
        curated.get("thesis")
        or envelope.get("thesis")
        or envelope.get("why_visit")
        or ""
    )

    # meta
    duration_min = route.get("duration_min") or theme.get("estimated_duration_min") or 0
    walk_m = route.get("walk_meters_est") or 0
    scenario = envelope.get("scenario") or ""

    # cast
    cast_raw = curated.get("cast") or envelope.get("cast") or []
    cast_names = [c["name"] for c in cast_raw if isinstance(c, dict) and c.get("name")]

    # prelude：从 envelope 已有字段拼装，不生成新文本
    prelude: list[str] = []
    if envelope.get("curator_note"):
        prelude.append(str(envelope["curator_note"]))
    if envelope.get("logic_line") and envelope["logic_line"] != envelope.get("curator_note"):
        prelude.append(str(envelope["logic_line"]))
    if envelope.get("aesthetic"):
        prelude.append(f"这一程的读法：{envelope['aesthetic']}。")
    if not prelude and envelope.get("why_visit"):
        prelude.append(str(envelope["why_visit"]))

    # chapter 结构来自 curated_story；正文/场景来自 blocks
    chapters_raw = curated.get("chapters") or envelope.get("chapters") or []
    story_cards: dict[int, dict[str, Any]] = {}
    scenes: dict[int, dict[str, Any]] = {}
    essays: dict[int, dict[str, Any]] = {}
    for b in blocks:
        if not isinstance(b, dict):
            continue
        t = b.get("type")
        order = b.get("stop_order")
        if t == "story_card" and isinstance(order, int):
            story_cards[order] = b
        elif t == "scene" and isinstance(order, int):
            scenes[order] = b
        elif t == "essay" and isinstance(order, int):
            essays[order] = b

    chapters: list[BookChapter] = []
    for ch in chapters_raw:
        if not isinstance(ch, dict):
            continue
        stop_id = ch.get("stopId") or ch.get("stop_id") or ch.get("index") or 0
        role = ch.get("narrativeRole") or ch.get("narrative_role") or "Anchor"
        ch_title = ch.get("title") or f"第 {ch.get('index', '?')} 站"
        # title 可能带「引子：和平饭店」这样的前缀；保留原样
        hook = ch.get("hook") or ""
        card = story_cards.get(stop_id, {})
        scene = scenes.get(stop_id)
        essay = essays.get(stop_id)
        body = _to_paragraphs(card.get("body") or "")
        essay_body = _to_paragraphs(essay.get("body") or "") if isinstance(essay, dict) else []
        sources = [
            BookSource(dataset=str(s.get("dataset", "")), record_id=str(s.get("record_id", "")))
            for s in (card.get("sources") or [])
            if isinstance(s, dict)
        ]
        chapters.append(
            BookChapter(
                index=int(ch.get("index", 0)),
                role=str(role),
                role_label=_ROLE_LABEL.get(str(role), str(role)),
                title=str(ch_title),
                hook=str(hook),
                relation=ch.get("relationToPrevious") or ch.get("relation_to_previous"),
                body_paragraphs=body,
                scene={
                    "place": str(scene.get("place", "")),
                    "today": str(scene.get("today", "")),
                    "era": str(scene.get("era_desc", "")),
                    "figures": str(scene.get("figures", "")),
                    "visual": str(scene.get("visual_note", "")),
                } if scene else None,
                sources=sources,
                walking_minutes=int(ch.get("walkingMinutes") or ch.get("walking_minutes") or 0),
                essay_title=str(essay.get("title", "")) if isinstance(essay, dict) else "",
                essay_paragraphs=essay_body,
            )
        )

    # 跋：收束语 + 路线回望
    epilogue: list[str] = []
    if chapters:
        epilogue.append(
            f"合上书页前，再走一遍这条线：{' → '.join(c.title for c in chapters)}。"
        )
    if envelope.get("why_visit"):
        epilogue.append(str(envelope["why_visit"]))
    epilogue.append(
        "目录给条目，我们给关系。每一处都来自可核对的开放数据，"
        "你随时可以合上这页，不算未完成。"
    )

    # 出处索引（去重）
    seen: set[str] = set()
    sources_index: list[BookSource] = []
    for ch in chapters:
        for s in ch.sources:
            key = f"{s.dataset}::{s.record_id}"
            if key not in seen:
                seen.add(key)
                sources_index.append(s)
    for s in envelope.get("sources") or []:
        if isinstance(s, str):
            key = f"source::{s}"
            if key not in seen:
                seen.add(key)
                sources_index.append(BookSource(dataset="source", record_id=s))

    # reading_line 从 hongyuan 元数据拼装
    hongyuan = envelope.get("hongyuan") or {}
    reading_line = hongyuan.get("summary") or " · ".join(
        str(hongyuan.get(k, {}).get("label", ""))
        for k in ("emotion", "narrative", "pacing")
        if isinstance(hongyuan.get(k), dict) and hongyuan[k].get("label")
    )

    return BookDoc(
        title=str(title),
        thesis=str(thesis),
        reading_line=reading_line,
        cast=cast_names,
        prelude=prelude,
        chapters=chapters,
        epilogue=epilogue,
        sources_index=sources_index,
        meta={
            "duration_min": duration_min,
            "walk_meters_est": walk_m,
            "scenario": scenario,
        },
        route_plan=_build_route_plan(envelope),
        review=envelope.get("curator_review") or {},
    )


def _build_route_plan(envelope: dict[str, Any]) -> dict[str, Any]:
    """从 route + intent 构建「路线规划页」结构化数据（纯读取，零 token）。

    导览手册形态的前置页：把行走计划显式呈现为可排程的行程表，
    便于读者按图索骥。所有字段均来自 envelope，不做任何生成。
    """
    import json as _json

    route = envelope.get("route") or {}
    stops = route.get("stops") or []
    intent = envelope.get("intent")
    if isinstance(intent, str):
        try:
            intent = _json.loads(intent)
        except Exception:
            logger.warning("book: intent JSON 解析失败，按空 dict 降级", exc_info=True)
            intent = {}
    if not isinstance(intent, dict):
        intent = {}

    overview = {
        "duration_min": route.get("duration_min") or 0,
        "walk_m": route.get("walk_meters_est") or 0,
        "stops": len(stops),
        "scenario": envelope.get("scenario") or intent.get("scene") or "",
        "audience": intent.get("audience") or "",
    }

    items: list[dict[str, Any]] = []
    for i, s in enumerate(stops):
        if not isinstance(s, dict):
            continue
        pitfalls = s.get("pitfalls") or {}
        items.append(
            {
                "index": i + 1,
                "name": s.get("name") or f"第 {i + 1} 站",
                "minutes": s.get("minutes") or 0,
                "meaning": (s.get("meaning") or "").strip(),
                "transition": (s.get("transition_to_next") or "").strip(),
                "open_hours": pitfalls.get("open_hours") or "未收录",
                "enterable": pitfalls.get("enterable") or "未收录",
                "need_reservation": pitfalls.get("need_reservation") or "未收录",
            }
        )

    return {"overview": overview, "stops": items}


def _chapter_html(ch: BookChapter) -> str:
    paras = "".join(f"<p>{html.escape(p)}</p>" for p in ch.body_paragraphs) or (
        '<p class="note">（本章叙事待生成）</p>'
    )
    scene_html = ""
    if ch.scene:
        parts = [
            ("舞台", ch.scene.get("place", "")),
            ("此刻", ch.scene.get("today", "")),
            ("年代", ch.scene.get("era", "")),
            ("人物", ch.scene.get("figures", "")),
        ]
        scene_items = " · ".join(
            f"<span class=\"k\">{k}</span>{html.escape(v)}"
            for k, v in parts if v
        )
        if scene_items:
            scene_html = f'<div class="scene">{scene_items}</div>'

    src_html = ""
    if ch.sources:
        src_html = (
            '<div class="srcs"><span class="k">出处</span>'
            + "、".join(html.escape(_label(s.dataset)) for s in ch.sources)
            + "</div>"
        )

    hook_html = f'<p class="hook">{html.escape(ch.hook)}</p>' if ch.hook else ""
    relation_html = (
        f'<p class="relation">{html.escape(ch.relation)}</p>'
        if ch.relation else ""
    )

    essay_html = ""
    if ch.essay_paragraphs:
        essay_title_html = (
            f'<div class="essay-kicker">{html.escape(ch.essay_title)}</div>'
            if ch.essay_title else ""
        )
        essay_paras = "".join(
            f"<p>{html.escape(p)}</p>" for p in ch.essay_paragraphs
        )
        essay_html = (
            '<div class="essay">'
            '<div class="essay-head"><span class="essay-tag">路线零件 · 长散文</span></div>'
            f"{essay_title_html}{essay_paras}</div>"
        )

    return f'''<section class="chapter">
  <h2>
    <span class="num">{str(ch.index).zfill(2)}</span>
    <span class="num-text">
      <span class="role">{html.escape(ch.role_label)}</span>
      <span class="title">{html.escape(ch.title)}</span>
    </span>
  </h2>
  {relation_html}
  {hook_html}
  {scene_html}
  {paras}
  {src_html}
  {essay_html}
</section>'''


def _toc_html(chapters: list[BookChapter]) -> str:
    items = "\n".join(
        f'<li><span class="ix">{str(c.index).zfill(2)}</span>'
        f'<span class="role">{html.escape(c.role_label)}</span>'
        f'<span class="title">{html.escape(c.title)}</span></li>'
        for c in chapters
    )
    return f'''<nav class="toc">
  <h2>目录</h2>
  <ol>{items}</ol>
</nav>'''


def _route_plan_html(route_plan: dict[str, Any]) -> str:
    if not route_plan or not route_plan.get("stops"):
        return ""
    ov = route_plan.get("overview", {})
    bits: list[str] = []
    if ov.get("duration_min"):
        bits.append(f"全程约 {ov['duration_min']} 分钟")
    if ov.get("walk_m"):
        bits.append(f"步行约 {ov['walk_m']} 米")
    if ov.get("stops"):
        bits.append(f"共 {ov['stops']} 站")
    if ov.get("scenario"):
        bits.append(str(ov["scenario"]))
    if ov.get("audience"):
        bits.append(f"适合{ov['audience']}")
    overview_line = " · ".join(bits)

    rows: list[str] = []
    for st in route_plan["stops"]:
        meaning = st.get("meaning") or ""
        first_line = meaning.split("。")[0].strip()[:70] if meaning else ""
        transition = st.get("transition") or ""
        open_info = (
            f"开放 {st.get('open_hours')} · 入内 {st.get('enterable')}"
            + (f" · 需预约 {st.get('need_reservation')}" if st.get("need_reservation") not in ("未收录", "", None) else "")
        )
        rows.append(
            f'''<li class="rp-stop">
  <span class="rp-num">{str(st['index']).zfill(2)}</span>
  <div class="rp-body">
    <div class="rp-name">{html.escape(st['name'])}<span class="rp-min">停留 {st['minutes']} 分钟</span></div>
    {f'<div class="rp-meaning">{html.escape(first_line)}</div>' if first_line else ''}
    <div class="rp-meta">{html.escape(open_info)}</div>
    {f'<div class="rp-next">下一站 · {html.escape(transition)}</div>' if transition else ''}
  </div>
</li>'''
        )
    rows_html = "\n".join(rows)
    return f'''<section class="routeplan">
  <h2>路线规划</h2>
  <span class="ornament-line"></span>
  <p class="rp-overview">{html.escape(overview_line)}</p>
  <ol class="rp-list">{rows_html}</ol>
  <p class="rp-note">本手册每站含「风景与历史 / 人物 / 游玩设计」三节，文末附出处索引，便于按图索骥。</p>
</section>'''


def render_book(envelope: dict[str, Any], *, include_toc: bool = True) -> str:
    """把 envelope 渲染成打印友好的单页 HTML。

    返回完整 HTML 文档（含样式），可直接在浏览器打开或走 wkhtmltopdf 转 PDF。
    """
    doc = _build_book_doc(envelope)

    prelude_html = ""
    if doc.prelude:
        prelude_html = (
            '<section class="prelude"><h2>序</h2><span class="ornament-line"></span>'
            + "".join(f"<p>{html.escape(p)}</p>" for p in doc.prelude)
            + "</section>"
        )

    epilogue_html = ""
    if doc.epilogue:
        epilogue_html = (
            '<section class="epilogue"><h2>跋</h2><span class="ornament-line"></span>'
            + "".join(f"<p>{html.escape(p)}</p>" for p in doc.epilogue)
            + "</section>"
        )

    review_data = _review_section_data(doc.review)
    review_html = _review_html(review_data) if review_data else ""

    cast_html = ""
    if doc.cast:
        cast_html = (
            '<div class="cast"><span class="k">出场人物</span>'
            + "、".join(html.escape(n) for n in doc.cast)
            + "</div>"
        )

    src_index_html = ""
    if doc.sources_index:
        src_index_html = (
            '<section class="srcindex"><h2>出处索引</h2><span class="ornament-line"></span><ul>'
            + "".join(
                f'<li><span class="ix">{str(i + 1).zfill(2)}</span>'
                f'<span class="dataset">{html.escape(_label(s.dataset))}</span>'
                f'<code>{html.escape(s.record_id)}</code></li>'
                for i, s in enumerate(doc.sources_index)
            )
            + "</ul></section>"
        )

    toc_html = _toc_html(doc.chapters) if include_toc else ""
    route_plan_html = _route_plan_html(doc.route_plan)
    chapters_html = "\n".join(_chapter_html(c) for c in doc.chapters)

    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>{html.escape(doc.title)} · RedTrip</title>
  <style>
@page {{ size: A4; margin: 22mm 18mm 18mm 18mm; }}
html {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
body {{
  margin: 0;
  padding: 0;
  font-family: "Noto Serif SC", "Songti SC", "Source Han Serif SC", Georgia, "Times New Roman", serif;
  color: #1a1410;
  line-height: 2.0;
  font-size: 11pt;
  background: #fff;
}}
.book {{
  max-width: 170mm;
  margin: 0 auto;
}}
.book-cover {{
  text-align: center;
  padding: 38mm 10mm 28mm;
  break-after: page;
  page-break-after: always;
}}
.book-cover .top-rule {{
  display: block;
  border-top: 0.5pt solid #b0925e;
  margin: 0 auto 22mm;
  width: 56mm;
}}
.book-cover .kicker {{
  font-family: "PingFang SC", "Helvetica Neue", sans-serif;
  font-size: 9pt;
  letter-spacing: 0.22em;
  color: #8a7a5e;
  margin: 0 0 26mm;
}}
.book-cover h1 {{
  font-size: 30pt;
  letter-spacing: 0.14em;
  margin: 0 0 16mm;
  font-weight: 600;
  line-height: 1.35;
}}
.book-cover .ornament {{
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8pt;
  margin: 10mm auto 14mm;
  width: 60mm;
}}
.book-cover .ornament .line {{ flex: 1; height: 0.5pt; background: #b0925e; }}
.book-cover .ornament .dot {{ width: 4pt; height: 4pt; background: #b0925e; transform: rotate(45deg); }}
.book-cover .thesis {{
  font-size: 12.5pt;
  color: #4a3f2e;
  font-style: italic;
  margin: 0 16mm 14mm;
  line-height: 2.05;
}}
.book-cover .reading {{
  font-size: 10.5pt;
  color: #4a3f2e;
  margin: 4mm 14mm 18mm;
  line-height: 2.0;
}}
.book-cover .meta {{
  font-family: "PingFang SC", "Helvetica Neue", sans-serif;
  font-size: 9pt;
  letter-spacing: 0.12em;
  color: #8a7a5e;
  margin: 18mm 0 0;
}}
.book-cover .seal {{
  display: inline-block;
  margin-top: 14mm;
  padding: 5pt 14pt;
  border: 1pt solid #b0925e;
  color: #b0925e;
  font-size: 10pt;
  letter-spacing: 0.3em;
  font-weight: 600;
}}

.toc, .prelude, .epilogue, .srcindex {{
  break-before: page;
  page-break-before: always;
  padding: 32mm 0 0;
}}
.toc h2, .prelude h2, .epilogue h2, .srcindex h2 {{
  font-family: "PingFang SC", "Helvetica Neue", sans-serif;
  font-size: 14pt;
  letter-spacing: 0.4em;
  text-align: center;
  margin: 0 0 12mm;
  border: none;
  font-weight: 600;
}}
.ornament-line {{
  display: block;
  width: 28mm;
  height: 1.5pt;
  background: #b0925e;
  margin: 0 auto 16mm;
}}
.toc ol {{
  list-style: none;
  padding: 0;
  margin: 0;
}}
.toc li {{
  display: flex;
  align-items: baseline;
  gap: 10pt;
  padding: 8pt 0;
  border-bottom: 0.5pt dotted #c9a45c;
}}
.toc li .ix {{
  font-family: Georgia, serif;
  color: #b0925e;
  flex-shrink: 0;
  width: 24pt;
}}
.toc li .role {{
  font-family: "PingFang SC", sans-serif;
  font-size: 9pt;
  color: #8a7a5e;
  letter-spacing: 0.12em;
  min-width: 4em;
}}
.toc li .title {{ flex: 1; }}

.prelude p, .epilogue p {{
  text-indent: 2em;
  text-align: justify;
  font-size: 11pt;
  margin: 0 0 6pt;
}}

.chapter {{
  break-before: page;
  page-break-before: always;
  padding: 4mm 0 0;
}}
.chapter h2 {{
  display: flex;
  align-items: flex-start;
  gap: 14pt;
  margin: 0 0 12mm;
  padding: 0;
  border: none;
}}
.chapter .num {{
  font-family: Georgia, "Times New Roman", serif;
  font-size: 40pt;
  color: #b0925e;
  line-height: 1;
  font-weight: 400;
  flex-shrink: 0;
}}
.chapter .num-text {{
  display: flex;
  flex-direction: column;
  gap: 6pt;
  padding-top: 4pt;
}}
.chapter .role {{
  font-family: "PingFang SC", "Helvetica Neue", sans-serif;
  font-size: 8.5pt;
  letter-spacing: 0.22em;
  color: #8a7a5e;
}}
.chapter .title {{
  font-size: 21pt;
  font-weight: 600;
  line-height: 1.35;
}}
.chapter .relation {{
  color: #6b5a36;
  font-size: 10.5pt;
  margin: 0 0 8mm;
}}
.chapter .hook {{
  font-style: italic;
  color: #4a3f2e;
  font-size: 11.5pt;
  margin: 0 0 8mm;
  padding: 0 0 0 8mm;
  border-left: 3pt solid #b0925e;
}}
.chapter .scene {{
  font-family: "PingFang SC", "Helvetica Neue", sans-serif;
  font-size: 9pt;
  color: #8a7a5e;
  margin: 0 0 8mm;
  padding: 4pt 0 4pt 8mm;
  border-left: 1pt solid #c9a45c;
}}
.chapter .scene .k {{
  display: inline-block;
  min-width: 3.5em;
  color: #b0925e;
  letter-spacing: 0.12em;
}}
.chapter p {{
  text-indent: 2em;
  text-align: justify;
  font-size: 11pt;
  line-height: 2.05;
  margin: 0 0 4pt;
}}
.chapter .note {{
  color: #8a7a5e;
  font-style: italic;
  text-indent: 0;
}}
.chapter .srcs {{
  font-family: "PingFang SC", "Helvetica Neue", sans-serif;
  font-size: 9pt;
  color: #8a7a5e;
  margin: 8mm 0 0;
  padding: 4pt 0 4pt 8mm;
  border-left: 3pt solid #b0925e;
}}
.chapter .srcs .k {{
  color: #b0925e;
  letter-spacing: 0.12em;
  margin-right: 0.6em;
}}

.chapter .essay {{
  margin: 10mm 0 0;
  padding: 6mm 0 0;
  border-top: 1pt solid #d8c39a;
}}
.chapter .essay-head {{
  margin: 0 0 4mm;
}}
.chapter .essay-tag {{
  display: inline-block;
  font-family: "PingFang SC", "Helvetica Neue", sans-serif;
  font-size: 8.5pt;
  letter-spacing: 0.22em;
  color: #8a7a5e;
  border: 0.5pt solid #c9a45c;
  padding: 1pt 8pt;
}}
.chapter .essay-kicker {{
  font-size: 12.5pt;
  font-weight: 600;
  color: #4a3f2e;
  margin: 0 0 3mm;
}}
.chapter .essay p {{
  text-indent: 2em;
  text-align: justify;
  font-size: 10.5pt;
  line-height: 2.0;
  margin: 0 0 4pt;
}}

.cast {{
  margin: 0 0 12mm;
  font-family: "PingFang SC", "Helvetica Neue", sans-serif;
  font-size: 9.5pt;
  color: #8a7a5e;
}}
.cast .k {{
  color: #b0925e;
  letter-spacing: 0.18em;
  margin-right: 0.8em;
}}

.srcindex ul {{
  list-style: none;
  padding: 0;
  margin: 0;
}}
.srcindex li {{
  display: flex;
  align-items: baseline;
  gap: 10pt;
  padding: 4pt 0;
  border-bottom: 0.5pt dotted #c9a45c;
  font-size: 10pt;
  color: #4a3f2e;
}}
.srcindex li .ix {{
  font-family: Georgia, serif;
  color: #b0925e;
  flex-shrink: 0;
  width: 18pt;
}}
.srcindex li .dataset {{ flex: 1; }}
.srcindex li code {{
  font-family: "SF Mono", "Menlo", monospace;
  font-size: 8.5pt;
  color: #8a7a5e;
}}

.routeplan {{
  break-before: page;
  page-break-before: always;
  padding: 30mm 0 0;
}}
.routeplan h2 {{
  font-family: "PingFang SC", "Helvetica Neue", sans-serif;
  font-size: 14pt;
  letter-spacing: 0.4em;
  text-align: center;
  margin: 0 0 10mm;
  border: none;
  font-weight: 600;
}}
.routeplan .rp-overview {{
  text-align: center;
  font-family: "PingFang SC", "Helvetica Neue", sans-serif;
  font-size: 10pt;
  letter-spacing: 0.14em;
  color: #8a7a5e;
  margin: 0 0 14mm;
}}
.routeplan .rp-list {{
  list-style: none;
  padding: 0;
  margin: 0;
}}
.routeplan .rp-stop {{
  display: flex;
  align-items: flex-start;
  gap: 12pt;
  padding: 10pt 0;
  border-bottom: 0.5pt dotted #c9a45c;
}}
.routeplan .rp-num {{
  font-family: Georgia, "Times New Roman", serif;
  font-size: 22pt;
  color: #b0925e;
  line-height: 1;
  font-weight: 400;
  flex-shrink: 0;
  width: 30pt;
}}
.routeplan .rp-body {{ flex: 1; }}
.routeplan .rp-name {{
  font-size: 14pt;
  font-weight: 600;
  display: flex;
  align-items: baseline;
  gap: 10pt;
}}
.routeplan .rp-min {{
  font-family: "PingFang SC", "Helvetica Neue", sans-serif;
  font-size: 8.5pt;
  letter-spacing: 0.12em;
  color: #8a7a5e;
  font-weight: 400;
}}
.routeplan .rp-meaning {{
  font-size: 10.5pt;
  color: #4a3f2e;
  text-indent: 0;
  margin: 4pt 0 0;
  line-height: 1.8;
}}
.routeplan .rp-meta {{
  font-family: "PingFang SC", "Helvetica Neue", sans-serif;
  font-size: 9pt;
  color: #8a7a5e;
  margin: 4pt 0 0;
}}
.routeplan .rp-next {{
  font-family: "PingFang SC", "Helvetica Neue", sans-serif;
  font-size: 9pt;
  color: #6b5a36;
  margin: 4pt 0 0;
  padding-left: 8mm;
  border-left: 1pt solid #c9a45c;
}}
.routeplan .rp-note {{
  font-size: 9.5pt;
  color: #8a7a5e;
  text-align: center;
  margin: 14mm 8mm 0;
  line-height: 1.9;
}}

.review {{
  break-before: page;
  page-break-before: always;
  padding: 28mm 0 0;
}}
.review h2 {{
  font-family: "PingFang SC", "Helvetica Neue", sans-serif;
  font-size: 14pt;
  letter-spacing: 0.4em;
  text-align: center;
  margin: 0 0 10mm;
  border: none;
  font-weight: 600;
}}
.review .review-note {{
  text-align: center;
  color: #8a7a5e;
  font-size: 10pt;
  margin: 0 10mm 10mm;
  line-height: 1.9;
}}
.review .k {{
  color: #b0925e;
  letter-spacing: 0.14em;
  margin-right: 0.6em;
}}
.review ul {{ list-style: none; padding: 0; margin: 4pt 0 8mm; }}
.review-warnings {{ margin: 0 0 8mm; }}
.review-warnings li, .review-concerns li {{
  border-left: 2pt solid #c9a45c;
  padding: 4pt 0 4pt 8mm;
  margin: 4pt 0;
  font-size: 10.5pt;
  line-height: 1.9;
}}
.review .rc-claim {{ margin: 0 0 2pt; text-indent: 0; }}
.review .rc-meta, .review .rc-fix {{
  font-size: 9.5pt;
  color: #6b5a36;
  margin: 0 0 2pt;
}}
.review .review-extras p {{ font-size: 10pt; color: #4a3f2e; margin: 6pt 0; }}

h1, h2 {{ break-after: avoid-page; page-break-after: avoid; break-inside: avoid; }}
.chapter .scene, .cast, .srcs, .hook {{ break-inside: avoid; page-break-inside: avoid; }}
p {{ orphans: 3; widows: 3; }}
  </style>
</head>
<body>
  <article class="book">
    <header class="book-cover">
      <span class="top-rule" aria-hidden></span>
      <p class="kicker">REDTRIP · 城市记忆策展人</p>
      <h1>{html.escape(doc.title)}</h1>
      <span class="ornament"><span class="line"></span><span class="dot"></span><span class="line"></span></span>
      {f'<p class="thesis">{html.escape(doc.thesis)}</p>' if doc.thesis else ""}
      {f'<p class="reading">{html.escape(doc.reading_line)}</p>' if doc.reading_line else ""}
      <p class="meta">约 {doc.meta.get('duration_min', 0)} 分钟 · 步行估 {doc.meta.get('walk_meters_est', 0)} 米 · {html.escape(doc.meta.get('scenario', ''))}</p>
      <p class="seal">可　·　溯　·　源</p>
    </header>
    {route_plan_html}
    {toc_html}
    {prelude_html}
    {chapters_html}
    {epilogue_html}
    {review_html}
    {cast_html}
    {src_index_html}
  </article>
</body>
</html>'''


def render_book_doc(envelope: dict[str, Any]) -> BookDoc:
    """返回结构化 BookDoc，供 EPUB/PDF 生成器进一步消费。"""
    return _build_book_doc(envelope)


# ─────────────────────────────────────────────────────────────────────────────
# 书籍化 P4：导出（MDX / EPUB / PDF）
#   以下全部为零 token 纯函数，仅消费 BookDoc / envelope，与 render_book 同构。
# ─────────────────────────────────────────────────────────────────────────────

def _mdx_safe(s: str) -> str:
    """MDX 安全转义：中文正文应不含 JSX 表达式字符，转义以防解析破坏。"""
    return (
        str(s)
        .replace("{", "&#123;")
        .replace("}", "&#125;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _md_yaml(s: Any) -> str:
    """YAML frontmatter 标量安全化：去换行、双引号转单引号。"""
    return str(s).replace("\n", " ").replace('"', "'")


def render_book_markdown(envelope: dict[str, Any], *, include_toc: bool = True) -> str:
    """渲染为 MDX 兼容的 Markdown（CommonMark + YAML frontmatter）。

    无原始 HTML、无 JSX 表达式字符（已转义），可直接当 .md 或 .mdx 使用。
    结构：frontmatter → 标题/命题 → 路线规划（表格）→ 目录 → 序 → 各章
    （风景与历史/人物/游玩设计）→ 跋 → 出处索引。
    """
    doc = _build_book_doc(envelope)
    L: list[str] = []

    # frontmatter
    fm = ["---", f'title: "{_md_yaml(doc.title)}"']
    if doc.thesis:
        fm.append(f'subtitle: "{_md_yaml(doc.thesis)}"')
    if doc.reading_line:
        fm.append(f'reading: "{_md_yaml(doc.reading_line)}"')
    if doc.meta.get("duration_min"):
        fm.append(f'duration_min: {doc.meta["duration_min"]}')
    if doc.meta.get("walk_meters_est"):
        fm.append(f'walk_meters_est: {doc.meta["walk_meters_est"]}')
    if doc.meta.get("scenario"):
        fm.append(f'scenario: "{_md_yaml(doc.meta["scenario"])}"')
    if doc.cast:
        fm.append(f'cast: [{", ".join(_md_yaml(c) for c in doc.cast)}]')
    fm.append("---")
    L.append("\n".join(fm))

    # 标题 / 命题 / 读法
    L.append("")
    L.append(f"# {_mdx_safe(doc.title)}")
    if doc.thesis:
        L.append("")
        L.append(f"> {_mdx_safe(doc.thesis)}")
    if doc.reading_line:
        L.append("")
        L.append(f"_{_mdx_safe(doc.reading_line)}_")

    # 路线规划
    if doc.route_plan and doc.route_plan.get("stops"):
        rp = doc.route_plan
        ov = rp.get("overview", {})
        bits: list[str] = []
        if ov.get("duration_min"):
            bits.append(f"全程约 {ov['duration_min']} 分钟")
        if ov.get("walk_m"):
            bits.append(f"步行约 {ov['walk_m']} 米")
        if ov.get("stops"):
            bits.append(f"共 {ov['stops']} 站")
        if ov.get("scenario"):
            bits.append(str(ov["scenario"]))
        if ov.get("audience"):
            bits.append(f"适合{ov['audience']}")
        L.append("")
        L.append("## 路线规划")
        if bits:
            L.append("")
            L.append("> " + " · ".join(bits))
        L.append("")
        L.append("| 站序 | 站名 | 停留 | 开放 / 可入内 | 通往下一站 |")
        L.append("| --- | --- | --- | --- | --- |")
        for st in rp["stops"]:
            open_info = f"开放 {st.get('open_hours')} / 入内 {st.get('enterable')}"
            need = st.get("need_reservation")
            if need not in ("未收录", "", None):
                open_info += f" / 需预约 {need}"
            L.append(
                f"| {st['index']} | {_mdx_safe(st['name'])} | {st['minutes']} 分钟 "
                f"| {open_info} | {_mdx_safe(st.get('transition') or '—')} |"
            )

    # 目录
    if include_toc and doc.chapters:
        L.append("")
        L.append("## 目录")
        for c in doc.chapters:
            L.append(f"- {str(c.index).zfill(2)} · {c.role_label} · {_mdx_safe(c.title)}")

    # 序
    if doc.prelude:
        L.append("")
        L.append("## 序")
        for p in doc.prelude:
            L.append("")
            L.append(_mdx_safe(p))

    # 各章
    for ch in doc.chapters:
        L.append("")
        L.append(f"## {str(ch.index).zfill(2)} · {ch.role_label} · {_mdx_safe(ch.title)}")
        if ch.relation:
            L.append("")
            L.append(f"_{_mdx_safe(ch.relation)}_")
        if ch.hook:
            L.append("")
            L.append(f"> {_mdx_safe(ch.hook)}")
        if ch.scene:
            sc = " · ".join(
                f"{k}：{v}"
                for k, v in (
                    ("舞台", ch.scene.get("place", "")),
                    ("此刻", ch.scene.get("today", "")),
                    ("年代", ch.scene.get("era", "")),
                    ("人物", ch.scene.get("figures", "")),
                )
                if v
            )
            if sc:
                L.append("")
                L.append(f"_{sc}_")
        for p in ch.body_paragraphs:
            L.append("")
            L.append(_mdx_safe(p))
        if ch.essay_paragraphs:
            L.append("")
            L.append("> 路线零件 · 长散文" + (f" — {_mdx_safe(ch.essay_title)}" if ch.essay_title else ""))
            for p in ch.essay_paragraphs:
                L.append("")
                L.append(_mdx_safe(p))
        if ch.sources:
            L.append("")
            L.append("出处：" + "、".join(_label(s.dataset) for s in ch.sources))

    # 跋
    if doc.epilogue:
        L.append("")
        L.append("## 跋")
        for p in doc.epilogue:
            L.append("")
            L.append(_mdx_safe(p))

    # 策展留白 · 反方策展人（gated）
    review_data = _review_section_data(doc.review)
    if review_data:
        L.extend(_review_markdown(review_data))

    # 出处索引
    if doc.sources_index:
        L.append("")
        L.append("## 出处索引")
        for i, s in enumerate(doc.sources_index, 1):
            L.append(f"{i}. {_label(s.dataset)} — `{s.record_id}`")

    return "\n".join(L)


# ── EPUB3（stdlib 零依赖）───────────────────────────────────────────────────

_EPUB_CSS = """
body { font-family: "Noto Serif SC", "Songti SC", serif; color: #1a1410;
  line-height: 1.9; font-size: 1.05em; margin: 0 1.2em; }
h1 { font-size: 1.8em; text-align: center; margin: 2.4em 0 0.6em; }
h2 { font-size: 1.35em; margin: 1.8em 0 0.6em; border-bottom: 1px solid #c9a45c;
  padding-bottom: 0.2em; }
.cover { text-align: center; padding: 4em 1em; }
.cover-title { font-size: 2.1em; letter-spacing: 0.08em; margin: 0 0 0.6em; }
.thesis { font-style: italic; color: #4a3f2e; margin: 1.2em 0; }
.reading { color: #4a3f2e; }
.meta { color: #8a7a5e; font-size: 0.85em; margin-top: 2em; letter-spacing: 0.1em; }
.seal { display: inline-block; margin-top: 1.6em; padding: 0.3em 1em;
  border: 1px solid #b0925e; color: #b0925e; letter-spacing: 0.3em; }
.num { color: #b0925e; font-family: Georgia, serif; }
.role { color: #8a7a5e; font-size: 0.8em; letter-spacing: 0.2em;
  display: block; margin-bottom: 0.2em; }
.hook { font-style: italic; color: #4a3f2e; border-left: 3px solid #b0925e;
  padding-left: 0.8em; margin: 1em 0; }
.scene { color: #8a7a5e; font-size: 0.9em; border-left: 1px solid #c9a45c;
  padding-left: 0.8em; margin: 1em 0; }
.scene .k { color: #b0925e; margin-right: 0.4em; }
.srcs { color: #8a7a5e; font-size: 0.9em; margin: 1em 0 0;
  border-left: 3px solid #b0925e; padding-left: 0.8em; }
.srcs .k { color: #b0925e; margin-right: 0.6em; letter-spacing: 0.1em; }
.essay { margin: 1.2em 0 0; padding-top: 0.8em; border-top: 1px solid #d8c39a; }
.essay-tag { color: #8a7a5e; font-size: 0.8em; letter-spacing: 0.2em;
  border: 1px solid #c9a45c; display: inline-block; padding: 0.1em 0.6em; margin: 0 0 0.6em; }
.essay-title { font-weight: 600; color: #4a3f2e; }
.review { margin: 2em 0 0; }
.review h2 { border: none; text-align: center; letter-spacing: 0.2em; }
.review-note { color: #8a7a5e; font-style: italic; }
.review .k { color: #b0925e; }
.review ul { list-style: none; padding: 0; }
.review-warnings li, .review-concerns li { border-left: 2px solid #c9a45c;
  padding-left: 0.8em; margin: 0.4em 0; }
.rc-claim { margin: 0; }
.rc-meta, .rc-fix { color: #6b5a36; font-size: 0.9em; }
p { text-indent: 2em; text-align: justify; margin: 0 0 0.6em; }
.relation { color: #6b5a36; font-style: italic; }
table { border-collapse: collapse; width: 100%; margin: 1em 0; font-size: 0.9em; }
th, td { border: 1px solid #c9a45c; padding: 0.4em 0.6em; text-align: left; }
th { background: #f3ecdd; }
.rp-stop { border-bottom: 1px dotted #c9a45c; padding: 0.6em 0; }
.rp-num { color: #b0925e; font-family: Georgia, serif; font-size: 1.4em;
  margin-right: 0.6em; }
.rp-name { font-weight: 600; }
.rp-min { color: #8a7a5e; font-size: 0.8em; }
.colophon li { margin: 0.4em 0; }
"""

_CONTAINER_XML = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<container version="1.0" '
    'xmlns="urn:oasis:names:tc:opendigitalmedia:xmlns:container">\n'
    '  <rootfiles>\n'
    '    <rootfile full-path="OEBPS/content.opf" '
    'media-type="application/oebps-package+xml"/>\n'
    '  </rootfiles>\n'
    '</container>\n'
)


def _xhtml_doc(title: str, inner: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<html xmlns="http://www.w3.org/1999/xhtml" '
        'xmlns:epub="http://www.idpf.org/2007/ops" lang="zh-CN" '
        'xml:lang="zh-CN">\n'
        '<head>\n<meta charset="utf-8"/>\n'
        f"<title>{html.escape(title)}</title>\n"
        '<link rel="stylesheet" type="text/css" href="style.css"/>\n'
        '</head>\n<body>\n' + inner + "\n</body>\n</html>\n"
    )


def _cover_inner(doc: BookDoc, vol_title: str) -> str:
    parts = [f'<div class="cover"><h1 class="cover-title">{html.escape(doc.title)}</h1>']
    if doc.thesis:
        parts.append(f'<p class="thesis">{html.escape(doc.thesis)}</p>')
    if doc.reading_line:
        parts.append(f'<p class="reading">{html.escape(doc.reading_line)}</p>')
    meta_bits = []
    if doc.meta.get("duration_min"):
        meta_bits.append(f"约 {doc.meta['duration_min']} 分钟")
    if doc.meta.get("walk_meters_est"):
        meta_bits.append(f"步行估 {doc.meta['walk_meters_est']} 米")
    if doc.meta.get("scenario"):
        meta_bits.append(html.escape(doc.meta["scenario"]))
    if meta_bits:
        parts.append('<p class="meta">' + " · ".join(meta_bits) + "</p>")
    parts.append('<p class="seal">可 · 溯 · 源</p></div>')
    return "\n".join(parts)


def _routeplan_inner(doc: BookDoc) -> str:
    rp = doc.route_plan
    if not rp or not rp.get("stops"):
        return '<p class="note">（本程无路线规划数据）</p>'
    ov = rp.get("overview", {})
    bits = []
    if ov.get("duration_min"):
        bits.append(f"全程约 {ov['duration_min']} 分钟")
    if ov.get("walk_m"):
        bits.append(f"步行约 {ov['walk_m']} 米")
    if ov.get("stops"):
        bits.append(f"共 {ov['stops']} 站")
    if ov.get("scenario"):
        bits.append(html.escape(str(ov["scenario"])))
    if ov.get("audience"):
        bits.append(f"适合{html.escape(str(ov['audience']))}")
    rows = []
    for st in rp["stops"]:
        open_info = f"开放 {st.get('open_hours')} / 入内 {st.get('enterable')}"
        need = st.get("need_reservation")
        if need not in ("未收录", "", None):
            open_info += f" / 需预约 {need}"
        rows.append(
            f'<div class="rp-stop"><span class="rp-num">{str(st["index"]).zfill(2)}</span>'
            f'<div class="rp-body"><div class="rp-name">{html.escape(st["name"])}'
            f'<span class="rp-min"> 停留 {st["minutes"]} 分钟</span></div>'
            f'<div class="rp-meta">{html.escape(open_info)}</div>'
            + (
                f'<div class="rp-next">下一站 · {html.escape(st.get("transition") or "")}</div>'
                if st.get("transition") else ""
            )
            + "</div></div>"
        )
    return (
        "<h2>路线规划</h2>"
        + (f'<p>{html.escape(" · ".join(bits))}</p>' if bits else "")
        + '<div class="rp-list">' + "".join(rows) + "</div>"
    )


def _prelude_inner(doc: BookDoc) -> str:
    if not doc.prelude:
        return ""
    parts = ["<h2>序</h2>"]
    parts.extend(f"<p>{html.escape(p)}</p>" for p in doc.prelude)
    return "\n".join(parts)


def _chapter_inner(ch: BookChapter) -> str:
    parts = [
        f'<h2><span class="num">{str(ch.index).zfill(2)}</span> '
        f'<span class="role">{html.escape(ch.role_label)}</span> '
        f"{html.escape(ch.title)}</h2>"
    ]
    if ch.relation:
        parts.append(f'<p class="relation">{html.escape(ch.relation)}</p>')
    if ch.hook:
        parts.append(f'<p class="hook">{html.escape(ch.hook)}</p>')
    if ch.scene:
        sc = " · ".join(
            f'<span class="k">{k}</span>{html.escape(v)}'
            for k, v in (
                ("舞台", ch.scene.get("place", "")),
                ("此刻", ch.scene.get("today", "")),
                ("年代", ch.scene.get("era", "")),
                ("人物", ch.scene.get("figures", "")),
            )
            if v
        )
        if sc:
            parts.append(f'<div class="scene">{sc}</div>')
    paras = "".join(f"<p>{html.escape(p)}</p>" for p in ch.body_paragraphs) or (
        '<p class="note">（本章叙事待生成）</p>'
    )
    parts.append(paras)
    if ch.essay_paragraphs:
        parts.append('<div class="essay"><p class="essay-tag">路线零件 · 长散文</p>')
        if ch.essay_title:
            parts.append(f'<p class="essay-title">{html.escape(ch.essay_title)}</p>')
        parts.append("".join(f"<p>{html.escape(p)}</p>" for p in ch.essay_paragraphs))
        parts.append("</div>")
    if ch.sources:
        parts.append(
            '<div class="srcs"><span class="k">出处</span>'
            + "、".join(html.escape(_label(s.dataset)) for s in ch.sources)
            + "</div>"
        )
    return "\n".join(parts)


def _epilogue_inner(doc: BookDoc) -> str:
    return "<h2>跋</h2>\n" + "\n".join(f"<p>{html.escape(p)}</p>" for p in doc.epilogue)


def _review_section_data(review: dict[str, Any]) -> dict[str, Any] | None:
    """从 curator_review 抽取可渲染内容；无有效内容则返回 None（不渲染）。"""
    if not isinstance(review, dict):
        return None
    warnings = [str(w) for w in (review.get("warnings") or []) if str(w).strip()]
    concerns = [c for c in (review.get("concerns") or []) if isinstance(c, dict)]
    missed = [str(v) for v in (review.get("missed_voices") or []) if str(v).strip()]
    alt = review.get("alternative_thesis")
    rev = review.get("reverse_route_note")
    if not (warnings or concerns or missed or alt or rev):
        return None
    return {
        "warnings": warnings,
        "concerns": concerns,
        "missed_voices": missed,
        "alternative_thesis": str(alt) if alt else "",
        "reverse_route_note": str(rev) if rev else "",
    }


def _review_html(data: dict[str, Any]) -> str:
    parts = [
        '<section class="review"><h2>策展留白 · 反方策展人</h2>'
        '<span class="ornament-line"></span>'
        '<p class="review-note">以下为对抗性评审留下的未决问题，不构成定论；'
        "它们指向值得在下一版或现场继续追问的方向。</p>"
    ]
    if data["warnings"]:
        parts.append(
            '<div class="review-warnings"><span class="k">评审告警</span><ul>'
            + "".join(f"<li>{html.escape(w)}</li>" for w in data["warnings"])
            + "</ul></div>"
        )
    if data["concerns"]:
        items = []
        for c in data["concerns"]:
            node = str(c.get("node") or "全路线")
            mech = str(c.get("mechanism") or "")
            fix = str(c.get("fix") or "")
            items.append(
                "<li>"
                f'<p class="rc-claim">{html.escape(str(c.get("claim") or ""))}</p>'
                f'<p class="rc-meta"><span class="k">节点</span>{html.escape(node)}'
                + (f' · <span class="k">机制</span>{html.escape(mech)}' if mech else "")
                + "</p>"
                + (f'<p class="rc-fix"><span class="k">改造</span>{html.escape(fix)}</p>' if fix else "")
                + "</li>"
            )
        parts.append(
            '<div class="review-concerns"><span class="k">反对意见</span><ul>'
            + "".join(items)
            + "</ul></div>"
        )
    extras = []
    if data["missed_voices"]:
        extras.append(
            '<p><span class="k">被忽略的声音</span>'
            + "、".join(html.escape(v) for v in data["missed_voices"])
            + "</p>"
        )
    if data["alternative_thesis"]:
        extras.append(
            '<p><span class="k">备选命题</span>'
            + html.escape(data["alternative_thesis"])
            + "</p>"
        )
    if data["reverse_route_note"]:
        extras.append(
            '<p><span class="k">反向走线</span>'
            + html.escape(data["reverse_route_note"])
            + "</p>"
        )
    if extras:
        parts.append('<div class="review-extras">' + "".join(extras) + "</div>")
    parts.append("</section>")
    return "".join(parts)


def _review_markdown(data: dict[str, Any]) -> list[str]:
    """返回追加在「跋」之后的 MDX 段落列表（不含空）。"""
    L: list[str] = ["", "## 策展留白 · 反方策展人", "",
                     "> 以下为对抗性评审留下的未决问题，不构成定论；它们指向值得在下一版或现场继续追问的方向。"]
    if data["warnings"]:
        L.append("")
        L.append("**评审告警**")
        for w in data["warnings"]:
            L.append(f"- {_mdx_safe(w)}")
    if data["concerns"]:
        L.append("")
        L.append("**反对意见**")
        for c in data["concerns"]:
            node = str(c.get("node") or "全路线")
            mech = str(c.get("mechanism") or "")
            fix = str(c.get("fix") or "")
            line = f"- {_mdx_safe(str(c.get('claim') or ''))}（节点：{_mdx_safe(node)}"
            if mech:
                line += f" · 机制：{_mdx_safe(mech)}"
            line += "）"
            L.append(line)
            if fix:
                L.append(f"  - 改造：{_mdx_safe(fix)}")
    if data["missed_voices"]:
        L.append("")
        L.append(f"**被忽略的声音**：{_mdx_safe('、'.join(data['missed_voices']))}")
    if data["alternative_thesis"]:
        L.append("")
        L.append(f"**备选命题**：{_mdx_safe(data['alternative_thesis'])}")
    if data["reverse_route_note"]:
        L.append("")
        L.append(f"**反向走线**：{_mdx_safe(data['reverse_route_note'])}")
    return L


def _review_epub_inner(data: dict[str, Any]) -> str:
    parts = [
        "<h2>策展留白 · 反方策展人</h2>"
        '<p class="review-note">以下为对抗性评审留下的未决问题，不构成定论；'
        "它们指向值得在下一版或现场继续追问的方向。</p>"
    ]
    if data["warnings"]:
        parts.append(
            '<p class="k">评审告警</p><ul>'
            + "".join(f"<li>{html.escape(w)}</li>" for w in data["warnings"])
            + "</ul>"
        )
    if data["concerns"]:
        items = []
        for c in data["concerns"]:
            node = str(c.get("node") or "全路线")
            mech = str(c.get("mechanism") or "")
            fix = str(c.get("fix") or "")
            items.append(
                "<li>"
                f'<p class="rc-claim">{html.escape(str(c.get("claim") or ""))}</p>'
                f'<p class="rc-meta"><span class="k">节点</span>{html.escape(node)}'
                + (f' · <span class="k">机制</span>{html.escape(mech)}' if mech else "")
                + "</p>"
                + (f'<p class="rc-fix"><span class="k">改造</span>{html.escape(fix)}</p>' if fix else "")
                + "</li>"
            )
        parts.append('<p class="k">反对意见</p><ul>' + "".join(items) + "</ul>")
    extras = []
    if data["missed_voices"]:
        extras.append('<p><span class="k">被忽略的声音</span>'
                      + "、".join(html.escape(v) for v in data["missed_voices"]) + "</p>")
    if data["alternative_thesis"]:
        extras.append('<p><span class="k">备选命题</span>'
                      + html.escape(data["alternative_thesis"]) + "</p>")
    if data["reverse_route_note"]:
        extras.append('<p><span class="k">反向走线</span>'
                      + html.escape(data["reverse_route_note"]) + "</p>")
    if extras:
        parts.append('<div class="review-extras">' + "".join(extras) + "</div>")
    return "\n".join(parts)


def _colophon_inner(doc: BookDoc) -> str:
    if not doc.sources_index:
        return '<h2>出处索引</h2><p class="note">（无出处记录）</p>'
    items = "\n".join(
        f'<li><span class="ix">{str(i + 1).zfill(2)}</span> '
        f'<span class="dataset">{html.escape(_label(s.dataset))}</span> '
        f'<code>{html.escape(s.record_id)}</code></li>'
        for i, s in enumerate(doc.sources_index)
    )
    return f'<h2>出处索引</h2>\n<ul class="colophon">{items}</ul>'


def _nav_xhtml(doc: BookDoc, sections: list[tuple[str, str, str]]) -> str:
    items = "\n".join(
        f'<li><a href="{href}">{html.escape(title)}</a></li>'
        for href, title, _kind in sections
    )
    return _xhtml_doc(doc.title, f'<nav epub:type="toc" id="toc"><h1>目录</h1><ol>{items}</ol></nav>')


def _opf_doc(doc: BookDoc, vol_title: str, sections: list[tuple[str, str, str]], vol_uid: str) -> str:
    modified = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest = [
        '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
        '<item id="css" href="style.css" media-type="text/css"/>',
    ]
    for href, _title, _kind in sections:
        item_id = href.rsplit(".", 1)[0]
        manifest.append(f'<item id="{item_id}" href="{href}" media-type="application/xhtml+xml"/>')
    spine = "".join(
        f'<itemref idref="{href.rsplit(".", 1)[0]}"/>' for href, _t, _k in sections
    )
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid" xml:lang="zh-CN">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="bookid">urn:uuid:{vol_uid}</dc:identifier>
    <dc:title>{html.escape(vol_title)}</dc:title>
    <dc:language>zh-CN</dc:language>
    <dc:creator>RedTrip · 城市记忆策展人</dc:creator>
    <meta property="dcterms:modified">{modified}</meta>
  </metadata>
  <manifest>
    {''.join(manifest)}
  </manifest>
  <spine>
    {spine}
  </spine>
</package>'''


def _split_chapter_groups(chapters: list[BookChapter], max_per: int) -> list[list[BookChapter]]:
    if max_per and max_per > 0 and len(chapters) > max_per:
        return [chapters[i : i + max_per] for i in range(0, len(chapters), max_per)]
    return [chapters]


def _build_epub_volume(
    doc: BookDoc,
    vol_title: str,
    chapters_in_vol: list[BookChapter],
    *,
    has_prelude: bool,
    has_epilogue: bool,
    vol_uid: str,
) -> bytes:
    """把单卷渲染为 EPUB3（ZIP）字节；每卷自包含（路线规划 + 本章段 + 出处索引）。"""
    sections: list[tuple[str, str, str]] = []
    sections.append(("cover.xhtml", vol_title, "cover"))
    sections.append(("routeplan.xhtml", "路线规划", "routeplan"))
    if has_prelude:
        sections.append(("prelude.xhtml", "序", "prelude"))
    for ch in chapters_in_vol:
        sections.append((f"chap-{str(ch.index).zfill(2)}.xhtml", ch.title, "chapter"))
    if has_epilogue:
        sections.append(("epilogue.xhtml", "跋", "epilogue"))
    review_data = _review_section_data(doc.review)
    if review_data:
        sections.append(("review.xhtml", "策展留白", "review"))
    sections.append(("colophon.xhtml", "出处索引", "colophon"))

    xhtml: dict[str, str] = {}
    xhtml["cover.xhtml"] = _xhtml_doc(vol_title, _cover_inner(doc, vol_title))
    xhtml["routeplan.xhtml"] = _xhtml_doc("路线规划", _routeplan_inner(doc))
    if has_prelude:
        xhtml["prelude.xhtml"] = _xhtml_doc("序", _prelude_inner(doc))
    for ch in chapters_in_vol:
        xhtml[f"chap-{str(ch.index).zfill(2)}.xhtml"] = _xhtml_doc(ch.title, _chapter_inner(ch))
    if has_epilogue:
        xhtml["epilogue.xhtml"] = _xhtml_doc("跋", _epilogue_inner(doc))
    if review_data:
        xhtml["review.xhtml"] = _xhtml_doc("策展留白", _review_epub_inner(review_data))
    xhtml["colophon.xhtml"] = _xhtml_doc("出处索引", _colophon_inner(doc))
    xhtml["nav.xhtml"] = _nav_xhtml(doc, sections)

    opf = _opf_doc(doc, vol_title, sections, vol_uid)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        # mimetype 必须是首个且未压缩条目（EPUB 规范）
        z.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/container.xml", _CONTAINER_XML)
        z.writestr("OEBPS/content.opf", opf)
        z.writestr("OEBPS/style.css", _EPUB_CSS)
        for href, content in xhtml.items():
            z.writestr(f"OEBPS/{href}", content)
    return buf.getvalue()


def _build_epub_volumes(doc: BookDoc, *, max_chapters_per_volume: int = 0) -> list[bytes]:
    groups = _split_chapter_groups(doc.chapters, max_chapters_per_volume)
    n = len(groups)
    out: list[bytes] = []
    for i, grp in enumerate(groups):
        single = n == 1
        vol_title = doc.title if single else f"{doc.title} · 第 {i + 1}/{n} 卷"
        out.append(
            _build_epub_volume(
                doc,
                vol_title,
                grp,
                has_prelude=single or i == 0,
                has_epilogue=single or i == n - 1,
                vol_uid=str(uuid.uuid4()),
            )
        )
    return out


def render_book_epub_bytes(envelope: dict[str, Any], *, max_chapters_per_volume: int = 0) -> bytes:
    """返回单卷 EPUB（ZIP）字节。多卷时返回第一卷；多卷请直接调用 write_epub。"""
    vols = _build_epub_volumes(_build_book_doc(envelope), max_chapters_per_volume=max_chapters_per_volume)
    return vols[0]


def write_epub(
    envelope: dict[str, Any], out_path: str, *, max_chapters_per_volume: int = 0
) -> list[str]:
    """写出 EPUB 文件（按需拆卷），返回各卷路径。"""
    doc = _build_book_doc(envelope)
    vols = _build_epub_volumes(doc, max_chapters_per_volume=max_chapters_per_volume)
    base = str(out_path)
    stem = base[:-5] if base.lower().endswith(".epub") else base
    paths: list[str] = []
    if len(vols) == 1:
        dest = base if base.lower().endswith(".epub") else base + ".epub"
        Path(dest).write_bytes(vols[0])
        paths.append(dest)
    else:
        for i, data in enumerate(vols, 1):
            dest = f"{stem}-vol{i}.epub"
            Path(dest).write_bytes(data)
            paths.append(dest)
    return paths


# ── PDF（best-effort wkhtmltopdf；否则沿用 render_book 的 @page A4 走浏览器打印）──

def render_book_pdf(envelope: dict[str, Any], out_path: str | None = None) -> bytes | None:
    """把书籍 HTML 经 wkhtmltopdf 转 PDF。

    - 返回 PDF 字节（out_path 为 None 时写临时文件再读回）；
    - 若环境中无 wkhtmltopdf，返回 None —— 调用方应提示用户用浏览器打开
      render_book 的 HTML 后「打印 → 另存为 PDF」（render_book 已含 @page A4 样式）。
    """
    wk = shutil.which("wkhtmltopdf") or shutil.which("wkhtmltopdf.exe")
    if not wk:
        return None
    html_doc = render_book(envelope)
    if out_path is None:
        import tempfile

        tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        tmp.close()
        target = tmp.name
    else:
        target = str(out_path)
    try:
        subprocess.run(
            [wk, "--quiet", "-s", "A4", "-T", "22", "-B", "18", "-L", "18", "-R", "18",
             "--encoding", "UTF-8", "-", target],
            input=html_doc.encode("utf-8"),
            check=True,
            capture_output=True,
        )
        return Path(target).read_bytes()
    except (subprocess.CalledProcessError, OSError) as exc:  # noqa: BLE001
        raise RuntimeError(f"wkhtmltopdf 生成 PDF 失败：{exc}") from exc
    finally:
        if out_path is None:
            try:
                Path(target).unlink()
            except OSError:
                pass
