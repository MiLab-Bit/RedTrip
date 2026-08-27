"""典籍新生 step③ demo：武康路全链路 + 新 render_book 典籍形态。

跑真实 curate()（SLC 取证 + LLM 润色），对最终 envelope 调用
render_book / render_book_markdown / render_book_epub_bytes，输出：
  /tmp/redtrip_demo/wukang_book.html
  /tmp/redtrip_demo/wukang_book.md
  /tmp/redtrip_demo/wukang_book.epub
  /tmp/redtrip_demo/wukang_envelope.json   （供前端 UI ① 消费）
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

REPO = Path("/opt/redtrip")
OUT = Path("/tmp/redtrip_demo")
OUT.mkdir(parents=True, exist_ok=True)

# load .env
_env = REPO / ".env"
if _env.exists():
    for _line in _env.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if not _line or _line.startswith("#") or "=" not in _line:
            continue
        _k, _v = _line.split("=", 1)
        os.environ.setdefault(_k.strip(), _v.strip().strip('"'))

for _d in ("packages/curator", "packages/library-client", "packages/gate"):
    sys.path.insert(0, str(REPO / _d))

from redtrip_curator.pipeline import curate  # noqa: E402
from redtrip_curator.book import (  # noqa: E402
    render_book,
    render_book_markdown,
    render_book_epub_bytes,
)


def main() -> int:
    slots = {
        "audience": "成人",
        "scene": "武康路—华山路一带",
        "duration_min": 90,
        "tone": "轻社交",
        "delivery": "路线",
        "companions": "2人",
    }
    message = "周末想带朋友走走武康路，感受老上海梧桐区里的文人气息和建筑故事，最好能挖出点有来历的人物和典故"
    print(f"[demo] scene={slots['scene']!r}")
    print(f"[demo] SLC_API_KEY set={bool(os.getenv('SLC_API_KEY'))} "
          f"LLM_API_BASE={os.getenv('LLM_API_BASE')} model={os.getenv('LLM_MODEL')}")
    t0 = time.time()
    result = curate(slots=slots, message=message)
    elapsed = time.time() - t0
    print(f"[demo] curate done in {elapsed:.1f}s ok={result.ok} mode={result.mode}")

    if not result.ok or result.envelope is None:
        print("[demo] FAILED:", result.reasons)
        return 2

    env = result.envelope

    # 验证 step③④ + 典籍形态数据源是否存在
    ca = env.get("curation_artifacts") or {}
    arc = ca.get("narrative_arc") or env.get("narrative_arc") or {}
    prov = ca.get("provenance") or env.get("provenance") or {}
    eg = ca.get("evidence_graph") or env.get("evidence_graph") or {}
    classical = [
        f for cl in eg.get("clusters", []) for f in cl.get("facts", [])
        if f.get("source_dataset") == "cbdb_classical" or f.get("layer") == "classical"
    ]
    print(f"[demo] narrative_arc nodes={len(arc.get('nodes', []))} "
          f"provenance aligned={prov.get('aligned_assertions')}/{prov.get('total_assertions')} "
          f"classical_facts={len(classical)}")

    # 渲染三形态
    html = render_book(env)
    (OUT / "wukang_book.html").write_text(html, encoding="utf-8")
    print(f"[demo] HTML {len(html)} bytes -> {OUT/'wukang_book.html'}")

    md = render_book_markdown(env)
    (OUT / "wukang_book.md").write_text(md, encoding="utf-8")
    print(f"[demo] MD {len(md)} bytes -> {OUT/'wukang_book.md'}")

    epub = render_book_epub_bytes(env)
    (OUT / "wukang_book.epub").write_bytes(epub)
    print(f"[demo] EPUB {len(epub)} bytes -> {OUT/'wukang_book.epub'}")

    # 存 envelope（前端 UI 消费）
    (OUT / "wukang_envelope.json").write_text(
        json.dumps(env, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[demo] envelope -> {OUT/'wukang_envelope.json'}")

    # 快速断言：典籍形态关键元素是否出现
    checks = {
        "扉页-考据缘起": "考据缘起" in html,
        "考据栏-考据": "考据" in html and "kj-label" in html,
        "验证章-验": "seal-ok" in html,
        "新发掘-标记": "badge-new" in html,
        "脚注-核验率": "可溯源核验率" in html,
        "CBDB回查链接": "cbdb.fas.harvard.edu" in html,
    }
    print("[demo] 典籍形态渲染检查:")
    for k, v in checks.items():
        print(f"  [{'OK' if v else 'MISS'}] {k}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
