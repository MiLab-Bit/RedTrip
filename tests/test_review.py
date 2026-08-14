"""反方策展人评审：review 模块 + 管线非阻断挂载 + 书籍附录渲染。

沙箱无 LLM 凭证，故用 monkeypatch 注入样例评审，验证：
- 评审只读取已生成叙事、不修改 envelope；
- warnings 非阻断（进入 notes，不回退模板）；
- concerns 上限 5 条；
- 书籍 HTML/MDX/EPUB 在 curator_review 存在时渲染「策展留白」附录，缺失时不渲染。
"""
import io
import zipfile

from redtrip_curator import pipeline as pipeline_mod
from redtrip_curator.book import (
    _review_section_data,
    render_book,
    render_book_epub_bytes,
    render_book_markdown,
)
from redtrip_curator.review import _review_payload, review_envelope

SAMPLE_REVIEW = {
    "concerns": [
        {"claim": "把鲁迅单一化为文化符号", "node": "鲁迅故居", "mechanism": "名人化", "fix": "补一位同时代普通编辑"},
        {"claim": "第二反对意见", "node": "全路线", "mechanism": "怀旧滤镜", "fix": "改"},
        {"claim": "第三", "node": "A", "mechanism": "m", "fix": "f"},
        {"claim": "第四", "node": "B", "mechanism": "m", "fix": "f"},
        {"claim": "第五", "node": "C", "mechanism": "m", "fix": "f"},
        {"claim": "第六（应被截断）", "node": "D", "mechanism": "m", "fix": "f"},
    ],
    "missed_voices": ["邻居", "店员"],
    "skipped_harder_node": "一处被拆除的工人宿舍",
    "alternative_thesis": "一条关于「谁的城市」的路线",
    "reverse_route_note": "从终点走回起点，叙事变成离散者的离城史",
    "warnings": ["D1: 鲁迅故居一段把「旧」自动等于价值", "W2: 参与者预设为文艺中产"],
}


def _env() -> dict:
    return {
        "theme": "t",
        "logic_line": "l",
        "why_visit": "w",
        "curator_note": "c",
        "route": {
            "stops": [
                {"order": 1, "name": "A", "meaning": "m1", "transition_to_next": "x"},
                {"order": 2, "name": "B", "meaning": "m2", "transition_to_next": None},
            ]
        },
        "blocks": [
            {"type": "story_card", "stop_order": 1, "body": "card A body"},
            {"type": "essay", "stop_order": 1, "body": "essay A body"},
            {"type": "story_card", "stop_order": 2, "body": "card B body"},
        ],
    }


def test_review_payload_structure():
    doc = _review_payload(_env(), None)
    assert set(doc["curatorial_thesis"]) >= {"theme", "logic_line", "why_visit", "curator_note"}
    assert len(doc["route_nodes"]) == 2
    assert doc["route_nodes"][0]["name"] == "A"
    # stop 1 同时含 card 与 essay；stop 2 仅 card
    by_stop = {d["stop_order"]: d for d in doc["narrative_by_stop"]}
    assert "card" in by_stop[1] and "essay" in by_stop[1]
    assert "card" in by_stop[2] and "essay" not in by_stop[2]


def test_review_envelope_extract_and_cap(monkeypatch):
    import redtrip_curator.review as review_mod

    monkeypatch.setattr(review_mod, "llm_configured", lambda: True)
    monkeypatch.setattr(review_mod, "chat_json", lambda **k: dict(SAMPLE_REVIEW))

    out = review_envelope(_env(), plan=None, voice=None)
    assert out is not None
    assert out["warnings"] == SAMPLE_REVIEW["warnings"]
    # concerns 封顶 5 条（第 6 条截断）
    assert len(out["concerns"]) == 5
    assert all(isinstance(c, dict) for c in out["concerns"])


def test_review_envelope_no_llm_returns_none(monkeypatch):
    import redtrip_curator.review as review_mod

    monkeypatch.setattr(review_mod, "llm_configured", lambda: False)
    assert review_envelope(_env()) is None


def test_review_envelope_does_not_mutate_envelope(monkeypatch):
    import redtrip_curator.review as review_mod

    monkeypatch.setattr(review_mod, "llm_configured", lambda: True)
    monkeypatch.setattr(review_mod, "chat_json", lambda **k: dict(SAMPLE_REVIEW))
    env = _env()
    before = env.get("curator_review")
    review_envelope(env)
    # envelope 不应被附带任何字段
    assert env.get("curator_review") is before


def test_review_section_data_gating():
    assert _review_section_data(None) is None
    assert _review_section_data({}) is None
    assert _review_section_data({"warnings": []}) is None
    data = _review_section_data(SAMPLE_REVIEW)
    assert data is not None
    assert data["warnings"] == SAMPLE_REVIEW["warnings"]
    # capping 是 review_envelope 的职责，本 helper 只透传
    assert data["concerns"] == SAMPLE_REVIEW["concerns"]


def test_book_appendix_renders_when_present():
    env = {"curator_review": SAMPLE_REVIEW}
    html = render_book(env)
    assert "策展留白" in html
    assert "鲁迅故居" in html
    assert "被忽略的声音" in html
    md = render_book_markdown(env)
    assert "策展留白" in md
    assert "备选命题" in md
    epub = render_book_epub_bytes(env)
    # EPUB 为 zip（xhtml 已压缩），解压后读取 review.xhtml 校验
    with zipfile.ZipFile(io.BytesIO(epub)) as z:
        assert "OEBPS/review.xhtml" in z.namelist()
        content = z.read("OEBPS/review.xhtml").decode("utf-8")
        assert "策展留白" in content


def test_book_appendix_absent_without_review():
    env = {}
    html = render_book(env)
    assert "策展留白" not in html
    md = render_book_markdown(env)
    assert "策展留白" not in md


def test_pipeline_review_non_blocking(monkeypatch):
    draft = _env()

    def fake_polish(*a, **k):
        return draft, ["polish note"], None

    class FakeVerdict:
        passed = True
        warnings = []

    monkeypatch.setattr(pipeline_mod, "llm_configured", lambda: True)
    monkeypatch.setattr(pipeline_mod, "polish_envelope", fake_polish)
    monkeypatch.setattr(pipeline_mod, "evaluate_envelope", lambda e: FakeVerdict())
    monkeypatch.setattr(pipeline_mod, "review_envelope", lambda *a, **k: dict(SAMPLE_REVIEW))

    env_out, notes, mode, _sp = pipeline_mod._finalize_narrative(draft, None, None)
    # 非阻断：仍返回 llm_polish，不回退模板
    assert mode == "llm_polish"
    assert env_out.get("curator_review") == SAMPLE_REVIEW
    # warnings 进入 notes
    assert any("评审" in n for n in notes)
    assert SAMPLE_REVIEW["warnings"][0] in notes


def test_pipeline_review_disabled_by_env(monkeypatch):
    draft = _env()

    def fake_polish(*a, **k):
        return draft, ["polish note"], None

    class FakeVerdict:
        passed = True
        warnings = []

    monkeypatch.setenv("REDTRIP_OPPOSING_CURATOR", "0")
    monkeypatch.setattr(pipeline_mod, "llm_configured", lambda: True)
    monkeypatch.setattr(pipeline_mod, "polish_envelope", fake_polish)
    monkeypatch.setattr(pipeline_mod, "evaluate_envelope", lambda e: FakeVerdict())
    called = {"n": 0}

    def fake_review(*a, **k):
        called["n"] += 1
        return dict(SAMPLE_REVIEW)

    monkeypatch.setattr(pipeline_mod, "review_envelope", fake_review)

    env_out, _notes, mode, _sp = pipeline_mod._finalize_narrative(draft, None, None)
    assert mode == "llm_polish"
    assert called["n"] == 0
    assert "curator_review" not in env_out
