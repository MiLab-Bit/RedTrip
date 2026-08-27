"""生成「路线零件长散文」预览：3 处相距甚远的上海坐标（武康大楼 / 提篮桥 / 龙华寺）。

用法（仓库根目录）：
  .venv/Scripts/python.exe scripts/gen_essay_preview.py
输出：
  <repo>/previews/essay_preview.html
  <repo>/previews/essay_preview.mdx
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
for _d in ("packages/curator", "packages/gate", "packages/library-client", "packages/tools", "apps/api"):
    _p = str(ROOT / _d)
    if Path(_p).is_dir() and _p not in sys.path:
        sys.path.insert(0, _p)

from redtrip_curator.book import render_book, render_book_markdown  # noqa: E402
from tests.test_essay import ESSAYS, _envelope, _three_stops  # noqa: E402

OUT = ROOT / "previews"

# 样例「反方策展人」评审：仅用于演示书籍附录「策展留白」的渲染形态，
# 非模型真实产出（沙箱无 LLM 凭证）。真实评审由 review.review_envelope 在
# 管线 Gate 通过后生成，写入 envelope["curator_review"]。
SAMPLE_REVIEW = {
    "concerns": [
        {
            "claim": "三站都选在「方便步行、方便拍照、方便叙述」的地标，回避了更难处理的工人新村与里弄拆迁现场。",
            "node": "全路线",
            "mechanism": "便利选址",
            "fix": "补一个被拆除/私有化的日常劳动空间作为对照节点。",
        },
        {
            "claim": "把武康大楼单一化为「船形公寓」的审美符号，弱化了它作为公寓楼里真实住户的生活。",
            "node": "武康大楼",
            "mechanism": "名人化/符号化",
            "fix": "补一位住户或管理者的口述，区分纪念与居住。",
        },
    ],
    "missed_voices": ["住户", "店员", "迁移者", "被纪念者的家人"],
    "skipped_harder_node": "一处已拆除的工人宿舍（城市更新中被抹去的空间）",
    "alternative_thesis": "一条关于「谁被留在了城市里、谁被请了出去」的路线",
    "reverse_route_note": "从龙华走回武康路，故事会变成离散者的离城史，而非名流的驻留史。",
    "warnings": [
        "D1: 武康大楼一段把「旧」自动等同于价值，未触及今日住户的租金压力。",
        "W2: 参与者被预设为具有同一文化资本与情感取向的人（中产、文艺、本地通）。",
    ],
}

env = _envelope(_three_stops(), essays=ESSAYS)
env["curator_review"] = SAMPLE_REVIEW
html = render_book(env)
mdx = render_book_markdown(env)

OUT.mkdir(parents=True, exist_ok=True)
(OUT / "essay_preview.html").write_text(html, encoding="utf-8")
(OUT / "essay_preview.mdx").write_text(mdx, encoding="utf-8")
print("wrote", OUT / "essay_preview.html", len(html), "chars")
print("wrote", OUT / "essay_preview.mdx", len(mdx), "chars")
