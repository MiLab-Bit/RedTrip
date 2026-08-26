"""book.py 测试：书籍化渲染器（零 token 纯函数）。"""
import io

from redtrip_curator.book import (
    _build_book_doc,
    render_book,
    render_book_epub_bytes,
    render_book_markdown,
)


def _make_envelope() -> dict:
    return {
        "theme": "外滩的世纪面孔",
        "why_visit": "用一栋楼的面孔读懂一座城的切换。",
        "curator_note": "从江海关到和平饭店，外滩不是风景线，而是时间线。",
        "aesthetic": "克制、留白、海派明信片",
        "scenario": "成人 · 2人 · 90分钟 · 步行约1200米 · 外滩",
        "route": {"duration_min": 90, "walk_meters_est": 1200, "stops": []},
        "blocks": [
            {
                "type": "story_card",
                "stop_order": 1,
                "title": "江海关：钟声里的主权",
                "body": "1927 年的江海关大楼顶上，大钟敲响的是租借对海关权力的接管。\n\n"
                        "这栋楼的前身是 1857 年的中式关署，1900 年代被拆。",
                "sources": [
                    {"dataset": "slc_building", "record_id": "r-海关-1"},
                ],
            },
            {
                "type": "scene",
                "stop_order": 1,
                "place": "江海关大楼",
                "today": "外滩 13 号",
                "era_desc": "1927 年建成",
                "figures": "海关总税务司",
                "city_thread": "从关署到钟楼",
                "visual_note": "钟楼四面可见",
            },
            {
                "type": "story_card",
                "stop_order": 2,
                "title": "和平饭店：身份切换",
                "body": "1929 年的华懋饭店，1956 年改名和平饭店。\n\n"
                        "同一栋楼的绿铜顶，见证了两种不同的城市身份。",
                "sources": [
                    {"dataset": "curated.landmark-facts", "record_id": "r-和平-1"},
                ],
            },
            {
                "type": "scene",
                "stop_order": 2,
                "place": "和平饭店",
                "today": "南京东路 20 号",
                "era_desc": "1929 年建成",
                "figures": "维克多·沙逊",
                "city_thread": "从华懋到和平",
                "visual_note": "绿铜顶",
            },
        ],
        "sources": ["上海图书馆开放数据", "OSM"],
        "curated_story": {
            "id": "book-1",
            "theme": {
                "id": "t-1",
                "title": "外滩的世纪面孔",
                "open_question": "外滩如何同时容纳海关、银行与饭店三种身份？",
                "research_axes": [],
                "why_visit": "用一栋楼的面孔读懂一座城的切换。",
                "estimated_duration_min": 90,
                "scope_note": "聚焦外滩建筑群",
            },
            "thesis": "外滩不是风景线，而是时间线。",
            "cast": [
                {"id": "ent-person-海关总税务司", "kind": "person", "name": "海关总税务司"},
                {"id": "ent-person-维克多·沙逊", "kind": "person", "name": "维克多·沙逊"},
                {"id": "ent-building-江海关大楼", "kind": "building", "name": "江海关大楼"},
                {"id": "ent-building-和平饭店", "kind": "building", "name": "和平饭店"},
            ],
            "chapters": [
                {
                    "id": "ch-1",
                    "index": 1,
                    "title": "引子：江海关大楼",
                    "hook": "钟声里，海关主权被写进建筑立面。",
                    "narrativeRole": "Hook",
                    "stopId": 1,
                    "relationToPrevious": None,
                    "evidenceIds": ["r-海关-1"],
                    "walkingMinutes": 10,
                    "castRefs": ["ent-building-江海关大楼", "ent-person-海关总税务司"],
                },
                {
                    "id": "ch-2",
                    "index": 2,
                    "title": "揭示：和平饭店",
                    "hook": "绿铜顶下，城市身份切换了两次。",
                    "narrativeRole": "Reveal",
                    "stopId": 2,
                    "relationToPrevious": "从江海关大楼走向和平饭店",
                    "evidenceIds": ["r-和平-1"],
                    "walkingMinutes": 15,
                    "castRefs": ["ent-building-和平饭店", "ent-person-维克多·沙逊"],
                },
            ],
            "evidenceGraph": {"theme_id": "t-1", "clusters": [], "joins": [], "coverage": {}},
            "quality": {"evidence_layers": 2, "coverage_ratio": 1.0, "aligned_ratio": 1.0},
        },
    }


def test_build_book_doc_extracts_chapters_and_scenes():
    doc = _build_book_doc(_make_envelope())
    assert doc.title == "外滩的世纪面孔"
    assert doc.thesis == "外滩不是风景线，而是时间线。"
    assert len(doc.cast) == 4
    assert len(doc.chapters) == 2
    ch1 = doc.chapters[0]
    assert ch1.index == 1
    assert ch1.role == "Hook"
    assert ch1.role_label == "引子"
    assert ch1.scene is not None
    assert ch1.scene["place"] == "江海关大楼"
    assert len(ch1.body_paragraphs) == 2
    ch2 = doc.chapters[1]
    assert ch2.relation == "从江海关大楼走向和平饭店"


def test_build_book_doc_sources_index_deduped():
    doc = _build_book_doc(_make_envelope())
    # 两章来源不同 + envelope.sources 归入 dataset="source"
    assert len(doc.sources_index) == 4
    datasets = {s.dataset for s in doc.sources_index}
    assert datasets == {"slc_building", "curated.landmark-facts", "source"}


def test_render_book_contains_cover_and_toc_and_chapters():
    html = render_book(_make_envelope())
    assert "外滩的世纪面孔" in html
    assert "目录" in html
    assert "江海关大楼" in html
    assert "和平饭店" in html
    assert "出处索引" in html
    assert "<!DOCTYPE html>" in html


def test_render_book_contains_route_plan_page():
    """导览手册形态：封面之后、目录之前应渲染「路线规划页」（行程表）。"""
    env = _make_envelope()
    env["route"] = {
        "duration_min": 90,
        "walk_meters_est": 1200,
        "stops": [
            {
                "name": "江海关大楼",
                "minutes": 10,
                "meaning": "钟声里，海关主权被写进建筑立面。",
                "transition_to_next": "从江海关走向和平饭店。",
                "pitfalls": {"open_hours": "9-17", "enterable": "可入内", "need_reservation": "无需"},
            },
            {
                "name": "和平饭店",
                "minutes": 15,
                "meaning": "绿铜顶下，城市身份切换了两次。",
                "transition_to_next": "",
                "pitfalls": {"open_hours": "未收录", "enterable": "未收录", "need_reservation": "未收录"},
            },
        ],
    }
    html = render_book(env)
    assert 'class="routeplan"' in html
    assert "路线规划" in html
    # 行程表含两站站名与停留时长
    assert "江海关大楼" in html and "和平饭店" in html
    assert "停留 10 分钟" in html and "停留 15 分钟" in html
    # 开放 / 可入内信息进入规划页
    assert "可入内 可入内" in html or "开放 9-17" in html
    # 路线规划页在目录之前（封面 → 路线规划 → 目录）
    assert html.find('class="routeplan"') < html.find(">目录<")


def test_render_book_markdown_has_frontmatter_and_sections():
    """书籍化 P4：MDX 导出含 YAML frontmatter 与封面/路线规划/目录/章/出处。"""
    env = _make_envelope()
    env["route"] = {
        "duration_min": 90,
        "walk_meters_est": 1200,
        "stops": [
            {
                "name": "江海关大楼", "minutes": 10,
                "meaning": "钟声里，海关主权被写进建筑立面。",
                "transition_to_next": "从江海关走向和平饭店。",
                "pitfalls": {"open_hours": "9-17", "enterable": "可入内", "need_reservation": "无需"},
            },
            {
                "name": "和平饭店", "minutes": 15,
                "meaning": "绿铜顶下，城市身份切换了两次。",
                "transition_to_next": "",
                "pitfalls": {"open_hours": "未收录", "enterable": "未收录", "need_reservation": "未收录"},
            },
        ],
    }
    md = render_book_markdown(env)
    assert md.startswith("---")
    assert 'title: "外滩的世纪面孔"' in md
    assert "# 外滩的世纪面孔" in md
    assert "## 路线规划" in md
    assert "## 目录" in md
    assert "## 序" in md
    assert "## 跋" in md
    assert "## 出处索引" in md
    # 章节标题带「序号 · 角色 · 站名」结构（fixture 的 title 自带角色前缀）
    assert "## 01 · 引子 · 引子：江海关大楼" in md


def test_render_book_markdown_route_plan_table_present():
    env = _make_envelope()
    env["route"] = {
        "duration_min": 90,
        "walk_meters_est": 1200,
        "stops": [
            {
                "name": "江海关大楼", "minutes": 10,
                "meaning": "钟声里，海关主权被写进建筑立面。",
                "transition_to_next": "从江海关走向和平饭店。",
                "pitfalls": {"open_hours": "9-17", "enterable": "可入内", "need_reservation": "无需"},
            },
            {
                "name": "和平饭店", "minutes": 15,
                "meaning": "绿铜顶下，城市身份切换了两次。",
                "transition_to_next": "",
                "pitfalls": {"open_hours": "未收录", "enterable": "未收录", "need_reservation": "未收录"},
            },
        ],
    }
    md = render_book_markdown(env)
    # 路线规划表格渲染出两站与停留时长
    assert "| 江海关大楼 | 10 分钟" in md
    assert "| 和平饭店 | 15 分钟" in md
    assert "开放 9-17 / 入内 可入内" in md


def test_render_book_epub_bytes_valid_zip_structure():
    """书籍化 P4：EPUB 导出为零依赖 ZIP，含 mimetype/container/opf/nav。"""
    import zipfile as _zip

    data = render_book_epub_bytes(_make_envelope())
    assert isinstance(data, bytes) and data[:2] == b"PK"  # ZIP 魔数
    with _zip.ZipFile(io.BytesIO(data)) as z:
        names = set(z.namelist())
        assert "mimetype" in names
        assert z.read("mimetype") == b"application/epub+zip"
        assert "META-INF/container.xml" in names
        assert "OEBPS/content.opf" in names
        assert "OEBPS/nav.xhtml" in names
        # 每章一个 XHTML
        chap_files = [n for n in names if n.startswith("OEBPS/chap-")]
        assert len(chap_files) == 2
        # OPF 声明 EPUB3
        opf = z.read("OEBPS/content.opf").decode("utf-8")
        assert 'version="3.0"' in opf
        assert "<dc:title>外滩的世纪面孔</dc:title>" in opf


def test_render_book_epub_volume_splitting():
    """书籍化 P4：超出 max_chapters_per_volume 时拆卷，每卷自包含路线规划与出处。"""
    import zipfile as _zip
    from redtrip_curator.book import _build_book_doc, _build_epub_volumes

    # 构造 5 章，每卷最多 2 章 → 应拆成 3 卷
    env = _make_envelope()
    doc = _build_book_doc(env)
    # 直接复制 chapters 凑出 5 章
    extra = list(doc.chapters)
    while len(extra) < 5:
        extra = extra + [c for c in doc.chapters]
    doc.chapters = extra[:5]
    vols = _build_epub_volumes(doc, max_chapters_per_volume=2)
    assert len(vols) == 3
    for v in vols:
        with _zip.ZipFile(io.BytesIO(v)) as z:
            n = z.namelist()
            assert "OEBPS/routeplan.xhtml" in n
            assert "OEBPS/colophon.xhtml" in n


def test_polish_card_target_is_soft_ceiling_not_floor():
    """去模板化：篇幅为软上限（仍引用 1500）、宁短勿注水（不再强制下限凑字数）。"""
    from redtrip_curator.polish import _CARD_TARGET_CHARS

    assert "1500" in _CARD_TARGET_CHARS
    assert "宁短" in _CARD_TARGET_CHARS
    assert "凑字数" in _CARD_TARGET_CHARS

