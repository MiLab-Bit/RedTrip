"""多城高德 API 验证：测 place_text 在苏州/杭州/扬州是否按城市返回 POI。"""
import os, sys
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
sys.path.insert(0, str(REPO / "packages/library-client"))

from redtrip_library.amap import AmapClient, amap_city_param

print("=== 城市→高德参数映射 ===")
for ck in ["shanghai", "suzhou", "hangzhou", "yangzhou", "nanjing", "jiaxing"]:
    print(f"  {ck} -> {amap_city_param(ck)}")

print("\n=== 高德按城市 POI 检索验证 ===")
client = AmapClient()
print(f"  key set: {bool(client.key)}")
tests = [
    ("suzhou", "拙政园"),
    ("hangzhou", "西湖"),
    ("yangzhou", "瘦西湖"),
    ("nanjing", "中山陵"),
]
for ck, kw in tests:
    pois = client.place_text(kw, city_key=ck, offset=5)
    if pois:
        p = pois[0]
        print(f"  [OK] {ck}/{kw}: 命中 {len(pois)} 条, 首条 {p['name']} @ ({p['lat']:.4f},{p['lng']:.4f}) {p.get('address') or ''}")
    else:
        print(f"  [MISS] {ck}/{kw}: 无结果（key 缺失或高德限流）")
