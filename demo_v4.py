"""典籍新生优化验证 v4：essay 关闭 + 全书编织 + 提示词新约束 + 溯源摘录。
确认：①耗时下降 ②weave 呼应句 ③body 无禁用词 ④classical excerpt 存在。
"""
import json, os, sys, time
from pathlib import Path
REPO = Path("/opt/redtrip")
OUT = Path("/tmp/redtrip_demo_v4")
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

slots = {"audience":"成人","scene":"武康路—华山路一带","duration_min":90,"tone":"轻社交","delivery":"路线","companions":"2人"}
msg = "周末想带朋友走走武康路，感受老上海梧桐区里的文人气息和建筑故事，最好能挖出点有来历的人物和典故"
t0 = time.time()
r = curate(slots=slots, message=msg)
elapsed = time.time() - t0
print(f"[v4] curate {elapsed:.1f}s ok={r.ok} narrative={r.narrative}")
print("[v4] WARNINGS:")
for w in (r.warnings or [])[:10]:
    print("   -", w)
print(f"[v4] 耗时对比: 之前 136-155s, 现在 {elapsed:.1f}s")

if not r.envelope:
    print("[v4] FAILED"); sys.exit(2)
env = r.envelope

# ① blocks 构成（essay 应关闭）
types = {}
for b in env.get("blocks", []):
    types[b.get("type")] = types.get(b.get("type"), 0) + 1
print(f"\n[v4] blocks: {types}")

# ② weave 呼应句（body 末尾应有「全书编织」追加痕迹——通过对比 note）
weave_notes = [w for w in (r.warnings or []) if "全书编织" in w]
print(f"\n[v4] 全书编织 notes: {len(weave_notes)} 条")
for n in weave_notes[:5]:
    print("   -", n)

# ③ body 无禁用词
from redtrip_gate.engine import FORBIDDEN_COPY
bad_in_bodies = []
for b in env.get("blocks", []):
    if b.get("type") == "story_card":
        body = b.get("body", "")
        for bad in FORBIDDEN_COPY:
            if bad in body:
                bad_in_bodies.append((b.get("stop_order"), bad))
print(f"\n[v4] story_card body 含禁用词: {bad_in_bodies if bad_in_bodies else '无'}")

# ④ classical excerpt 存在
classical_excerpts = 0
for stop in env.get("route", {}).get("stops", []):
    for l in stop.get("layers", []):
        if l.get("kind") == "classical" and (l.get("source") or {}).get("excerpt"):
            classical_excerpts += 1
print(f"[v4] classical 层带 excerpt: {classical_excerpts} 处")

# 存 envelope
(OUT / "wukang_envelope.json").write_text(
    json.dumps(env, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"[v4] envelope saved")
