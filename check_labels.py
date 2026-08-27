"""验证后端数据集中文映射 + 渲染产物含中文标签。"""
import json, os, sys
from pathlib import Path
REPO = Path("/opt/redtrip")
for _d in ("packages/curator", "packages/library-client", "packages/gate"):
    sys.path.insert(0, str(REPO / _d))
from redtrip_curator.book import render_book, _label

print("=== _label 映射检查 ===")
for ds in ["building_detail", "building_detail.relation", "building_detail.timeline",
           "event_list", "geonames_corpus", "literary_corpus", "cbdb_classical",
           "R-20 whitelist", "souyun_poem", "slc_building", "slc_era", "slc_poem"]:
    lbl = _label(ds)
    flag = "" if lbl != ds else "  <<< STILL ENGLISH"
    print(f"  {ds!r:40} -> {lbl}{flag}")

print("\n=== 渲染产物中文标签检查 ===")
env_path = Path("/tmp/redtrip_demo_v3/wukang_envelope.json")
if env_path.exists():
    env = json.loads(env_path.read_text(encoding="utf-8"))
    html = render_book(env)
    # 检查英文 dataset 是否还裸奔在 HTML 里
    bad = [ds for ds in ["building_detail.relation", "building_detail.timeline",
                         "event_list", "R-20 whitelist", "souyun_poem"]
           if ds in html]
    print(f"  HTML 中残留英文 dataset: {bad if bad else '无（全部中文化）'}")
    for ds in ["馆藏时间线", "人物关系", "事件记载", "R-20 白名单", "搜韵诗词",
               "CBDB 历代人物传记", "馆藏建筑", "地名志", "文学交集"]:
        if ds in html:
            print(f"  [OK] 出现「{ds}」")
else:
    print("  envelope 不存在，跳过渲染检查")
