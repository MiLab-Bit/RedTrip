"""典籍新生 v3 验证：跑 curate，保存润色后 envelope + 渲染 HTML/MD/EPUB。
确认 A-fix+B+C 后的叙事正文是「人物/记载主线」而非字段堆叠。
"""
import json, os, sys, time
from pathlib import Path
REPO = Path("/opt/redtrip")
OUT = Path("/tmp/redtrip_demo_v3")
OUT.mkdir(parents=True, exist_ok=True)

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

from redtrip_curator.pipeline import curate
from redtrip_curator.book import render_book, render_book_markdown, render_book_epub_bytes

slots = {"audience":"成人","scene":"武康路—华山路一带","duration_min":90,"tone":"轻社交","delivery":"路线","companions":"2人"}
msg = "周末想带朋友走走武康路，感受老上海梧桐区里的文人气息和建筑故事，最好能挖出点有来历的人物和典故"
t0 = time.time()
r = curate(slots=slots, message=msg)
print(f"[v3] curate {time.time()-t0:.1f}s ok={r.ok} narrative={r.narrative}")
print("[v3] WARNINGS:")
for w in (r.warnings or [])[:8]:
    print("   -", w)

if not r.envelope:
    print("[v3] FAILED"); sys.exit(2)

env = r.envelope

# 各 story_card body 开篇
print("\n[v3] story_card 开篇:")
for b in env.get("blocks", []):
    if b.get("type") == "story_card":
        body = b.get("body", "")
        is_template = body.lstrip().startswith("地址：") or ("开放数据将该建筑" in body[:100] and "据上海图书馆" in body[-30:])
        print(f"   stop{b.get('stop_order')}: {'TEMPLATE' if is_template else 'POLISHED'} | {body[:80].replace(chr(10),' ')}")

# 渲染三形态
html = render_book(env)
(OUT / "wukang_book.html").write_text(html, encoding="utf-8")
md = render_book_markdown(env)
(OUT / "wukang_book.md").write_text(md, encoding="utf-8")
epub = render_book_epub_bytes(env)
(OUT / "wukang_book.epub").write_bytes(epub)
(OUT / "wukang_envelope.json").write_text(json.dumps(env, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\n[v3] HTML {len(html)} bytes")
print(f"[v3] MD {len(md)} bytes")
print(f"[v3] EPUB {len(epub)} bytes")
print(f"[v3] envelope saved")
