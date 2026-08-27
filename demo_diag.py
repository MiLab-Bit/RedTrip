"""诊断：润色是否生效、Gate 是否拦截、为什么 body 是模板。"""
import json, os, sys, time
from pathlib import Path
REPO = Path("/opt/redtrip")
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
from redtrip_gate import evaluate_envelope

slots = {"audience":"成人","scene":"武康路—华山路一带","duration_min":90,"tone":"轻社交","delivery":"路线","companions":"2人"}
msg = "周末想带朋友走走武康路，感受老上海梧桐区里的文人气息和建筑故事，最好能挖出点有来历的人物和典故"
t0 = time.time()
r = curate(slots=slots, message=msg)
print(f"[diag] curate {time.time()-t0:.1f}s ok={r.ok} narrative={r.narrative} mode={r.mode}")
print("[diag] REASONS:", r.reasons)
print("[diag] WARNINGS (前 8 条):")
for w in (r.warnings or [])[:8]:
    print("   -", w)

if r.envelope:
    env = r.envelope
    # 各 story_card body 是否润色（模板含「地址：」开头）
    print("\n[diag] story_card body 检查:")
    for b in env.get("blocks", []):
        if b.get("type") == "story_card":
            body = b.get("body", "")
            is_template = body.lstrip().startswith("地址：") or "未收录" in body[:200]
            print(f"   stop{b.get('stop_order')}: {'TEMPLATE' if is_template else 'POLISHED'} | 前60字: {body[:60].replace(chr(10),' ')}")
    # 外层 Gate 重新评估
    verdict = evaluate_envelope(env)
    print(f"\n[diag] 外层 Gate: passed={verdict.passed}")
    print(f"[diag] Gate blockers (前 5): {verdict.blockers[:5]}")
    print(f"[diag] Gate warnings (前 5): {verdict.warnings[:5]}")
