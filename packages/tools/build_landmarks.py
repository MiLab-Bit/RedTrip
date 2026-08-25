#!/usr/bin/env python3
"""上海地标分类词库构建脚本（RAG 检索分类词条 → 批量拉取 → 分级入库）。

思路：不靠手写词库。定义两级分类词条体系（每个分类配高德搜索词 +
type 过滤规则），按词条分页检索高德 POI（city=021），过滤去重后带
分类号一次性写入 content/curated/shanghai-landmarks.json。

用法（服务器，无代理，.env 需含 REDTRIP_AMAP_KEY / REDTRIP_AMAP_SIG）:
    cd /opt/redtrip && /opt/redtrip/.venv/bin/python packages/tools/build_landmarks.py

输出结构:
    {
      "version": 1,
      "built_at": "...",
      "source": "amap place/text (city=021)",
      "categories": [{"id": "historic", "label": "历史建筑风貌"}, ...],
      "landmarks": [
        {"id": "historic-0001", "name": "...", "category_id": "historic",
         "category": "历史建筑风貌", "amap_type": "...", "address": "...",
         "lat": 31.23, "lng": 121.49}
      ]
    }
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "packages", "library-client"))

from redtrip_library.amap import AmapClient  # noqa: E402

OUT = os.path.join(ROOT, "content", "curated", "shanghai-landmarks.json")
PAGE_SIZE = 25
MAX_PAGES = 2          # 每词条最多 2 页（50 条候选）
RATE_LIMIT_S = 0.6     # 高德个人版 QPS 低，稳妥限速

# ---------------------------------------------------------------------------
# 两级分类词条体系（category_id / label / 高德搜索词 / 保留 type 前缀）
# 顺序即优先级：culture/historic/waterfront 先入库占 cell（去重先到先得），
# 避免「纪念馆/美术馆」这类跨类词被 persona 抢走分类。
# ---------------------------------------------------------------------------
CATEGORIES: list[dict[str, object]] = [
    {
        "id": "culture",
        "label": "博物馆美术馆文化场馆",
        "queries": ["博物馆", "美术馆", "艺术馆", "艺术中心", "科技馆", "展览馆",
                    "文化馆", "图书馆", "剧场", "音乐厅", "天文馆", "海洋馆", "海洋公园"],
        "keep": ["科教文化服务", "风景名胜"],
        "dayparts": ["day", "full"],
    },
    {
        "id": "historic",
        "label": "历史建筑风貌",
        "queries": ["历史建筑", "优秀历史建筑", "老建筑", "万国建筑", "老洋房",
                    "石库门", "里弄", "公馆", "别墅"],
        "keep": ["风景名胜", "历史古迹", "科教文化服务"],
        "dayparts": ["day", "full"],
    },
    {
        "id": "waterfront",
        "label": "滨水景观地标",
        "queries": ["滨江", "滨河", "码头", "外滩", "观光平台", "观景台", "广场",
                    "东方明珠", "上海中心", "金茂大厦", "环球金融中心", "陆家嘴",
                    "滴水湖", "苏州河", "黄浦江"],
        "keep": ["风景名胜", "公园广场"],
        "dayparts": ["day", "night", "full"],
    },
    {
        "id": "persona",
        "label": "名人故居纪念馆",
        "queries": ["名人故居", "故居", "纪念馆", "旧居"],
        "keep": ["风景名胜", "科教文化服务", "历史古迹"],
        "dayparts": ["day", "full"],
    },
    {
        "id": "nature",
        "label": "公园绿地湖泊",
        "queries": ["公园", "绿地", "滨江公园", "湿地", "植物园", "动物园"],
        "keep": ["公园广场", "风景名胜"],
        "dayparts": ["day", "full", "suburb"],
    },
    {
        "id": "religion",
        "label": "宗教场所",
        "queries": ["教堂", "寺庙", "清真寺", "道观", "礼拜堂"],
        "keep": ["宗教", "风景名胜", "历史古迹"],
        "dayparts": ["day", "full"],
    },
    {
        "id": "commercial",
        "label": "商业街区老字号",
        "queries": ["步行街", "商业街", "创意园", "老字号", "文创园", "艺术园区",
                    "新天地", "田子坊", "思南公馆", "石库门建筑群", "武康路"],
        "keep": ["购物服务", "风景名胜", "科教文化服务"],
        "dayparts": ["day", "night", "full"],
    },
    {
        "id": "nightlife",
        "label": "夜景夜生活",
        "queries": ["酒吧街", "夜市", "夜景", "夜生活", "灯光秀"],
        "keep": ["休闲娱乐", "餐饮服务", "购物服务", "风景名胜"],
        "dayparts": ["night", "full"],
    },
    {
        "id": "suburb",
        "label": "郊区自然古镇",
        "queries": ["古镇", "老街", "郊野公园", "森林公园", "农庄", "花海",
                    "生态园", "度假村", "滴水湖", "南汇"],
        "keep": ["风景名胜", "公园广场"],
        "dayparts": ["suburb", "full"],
    },
]

# name 硬黑名单：无 citywalk 价值的纯功能点
_DROP_NAME_KEYWORDS = (
    "派出所", "公安", "政务", "政府", "法院", "检察院", "城管", "消防",
    "通信", "通讯", "邮政", "电信", "移动", "联通",
    "加油站", "加气站", "停车场", "收费站", "驾校",
    "银行", "信用社", "ATM", "医院", "卫生院", "诊所", "药店", "药房",
    "快递", "物流", "殡仪", "墓地", "陵园",
    "写字楼", "商务中心", "办公楼", "大厦",
    "停车点", "有限公司", "分公司", "有限公司", "公司",
    # 经济连锁酒店（无参观价值）
    "如家", "汉庭", "亚朵", "全季", "桔子", "7天", "七天", "锦江之星",
    "格林豪泰", "速8", "速八", "城市便捷", "维也纳", "宜必思", "轻居",
    "智选假日", "希尔顿欢朋", "戴斯",
    # 普通快餐/小吃（无氛围）
    "馄饨", "米线", "麻辣烫", "沙县", "兰州拉面", "黄焖鸡", "鸭血粉丝",
    "面馆", "快餐", "小吃", "盒饭",
    "公厕", "洗手间", "地铁站", "公交站", "小区", "住宅",
)

# type 黑名单前缀（即使 type 白名单之外也兜底丢）
_DROP_TYPE_PREFIXES = (
    "住宿服务",      # 普通住宿（五星/豪华另由 _LUXURY 规则保留）
    "金融保险", "医疗保健", "汽车服务", "汽车维修", "交通设施",
    "道路附属", "地名地址", "商务住宅",
)

# 名校（保留）
_FAMOUS_UNIVERSITIES = (
    "复旦大学", "上海交通大学", "同济大学", "华东师范大学", "上海财经大学",
    "华东理工大学", "东华大学", "上海外国语大学", "上海大学", "上海科技大学",
    "上海纽约大学", "上海音乐学院", "上海戏剧学院", "华东政法大学",
    "上海理工大学", "上海师范大学", "上海海事大学", "上海海洋大学",
    "上海电力大学", "上海对外经贸大学",
)

# 豪华酒店品牌（保留）
_LUXURY_HOTEL_BRANDS = (
    "和平饭店", "半岛", "华尔道夫", "瑞吉", "柏悦", "君悦", "丽思卡尔顿",
    "宝格丽", "悦榕庄", "安缦", "瑰丽", "文华东方", "四季", "洲际",
    "外滩茂悦", "W酒店", "威斯汀", "香格里拉", "凯悦", "万达瑞华",
    "养云安缦", "朱家角安麓", "阿纳迪",
)

# 知名地标建筑（type 多为「商务住宅;楼宇」但 citywalk 必去——如陆家嘴三件套）
_LANDMARK_BUILDINGS = (
    "东方明珠", "上海中心", "金茂大厦", "环球金融中心", "上海环球港",
    "上海世茂广场", "白玉兰广场", "国际金融中心", "国金中心", "恒隆广场",
    "太古里", "来福士", "大悦城", "K11", "天安千树", "上生新所",
    "大丸百货", "新世界城", "第一百货", "久光百货", "上海商城",
    "静安嘉里中心", "港汇恒隆", "上海展览中心", "世博源", "上海大剧院",
)

# type 保留前缀（有 citywalk 价值的大类）
_KEEP_TYPE_PREFIXES = (
    "风景名胜", "科教文化服务", "公园广场", "博物馆", "历史古迹",
    "宗教", "餐饮服务", "购物服务", "休闲娱乐", "体育休闲",
)


def _is_valuable(name: str, t: str) -> bool:
    """返回该 POI 是否具备 citywalk 价值（黑名单式丢弃）。"""
    if not name:
        return False
    # 分店噪音：name 含「(xx店)」/「（xx店）」这类连锁分店后缀 → 丢
    if ("店)" in name or "店）" in name) and any(
        c in name for c in "()（）"
    ):
        return False
    if any(kw in name for kw in _DROP_NAME_KEYWORDS):
        return False
    if any(kw in name for kw in _FAMOUS_UNIVERSITIES):
        return True
    if any(b in name for b in _LUXURY_HOTEL_BRANDS):
        return True
    if any(b in name for b in _LANDMARK_BUILDINGS):
        return True
    if "五星级宾馆" in t or "豪华" in t:
        return True
    if t:
        if any(t.startswith(p) for p in _DROP_TYPE_PREFIXES):
            return False
        # 学校：非名校一律丢（名校已在上面保留）
        if any(k in t for k in ("学校", "高等院校", "中学", "小学", "大学")) or any(
            k in name for k in ("大学城", "校区", "学院", "附中", "附小", "职业学校")
        ):
            return False
        if any(t.startswith(p) for p in _KEEP_TYPE_PREFIXES):
            return True
        return False
    # type 为空：名字含地标词才保留
    return any(
        kw in name
        for kw in ("湖", "馆", "山", "寺", "塔", "古镇", "老街", "故居", "遗址",
                   "公园", "广场", "码头", "桥", "花园", "庄园", "湾", "岛",
                   "文化", "艺术", "博物馆", "教堂", "剧院", "音乐厅")
    )


def _norm_name(name: str) -> str:
    return name.strip().replace(" ", "").replace("\u3000", "")


def _cell_key(lng: float, lat: float) -> str:
    # 坐标网格去重：~100m 粒度（GCJ-02）
    return f"{lng:.3f},{lat:.3f}"


def main() -> int:
    env = {}
    for line in open(os.path.join(ROOT, ".env"), encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k] = v.strip().strip('"').strip("'")
    os.environ.setdefault("REDTRIP_AMAP_KEY", env.get("REDTRIP_AMAP_KEY", ""))
    os.environ.setdefault("REDTRIP_AMAP_SIG", env.get("REDTRIP_AMAP_SIG", ""))

    client = AmapClient()
    if not client.key:
        print("FATAL: REDTRIP_AMAP_KEY 未配置")
        return 1

    seen_cell: dict[str, str] = {}   # cell -> name（跨词条去重，优先留先到的）
    landmarks: list[dict[str, object]] = []
    total_requests = 0

    for cat in CATEGORIES:
        cid = cat["id"]
        label = cat["label"]
        queries = cat["queries"]
        keep = cat["keep"]
        for q in queries:
            for page in range(1, MAX_PAGES + 1):
                total_requests += 1
                pois = client.place_text(q, offset=PAGE_SIZE, page=page)
                if not pois:
                    break  # 空页提前停
                for p in pois:
                    name = _norm_name(str(p.get("name") or ""))
                    t = str(p.get("type") or "")
                    if not name or not _is_valuable(name, t):
                        continue
                    # 分类 keep 校验：type 必须命中本类 keep 前缀（type 空则放行，靠名字）；
                    # 知名地标建筑（如陆家嘴三件套 type=商务住宅;楼宇）不受此限
                    if t and keep and not any(t.startswith(k) for k in keep):
                        if not any(b in name for b in _LANDMARK_BUILDINGS):
                            continue
                    cell = _cell_key(float(p["lng"]), float(p["lat"]))
                    if cell in seen_cell:
                        continue  # 与更早词条重复
                    seen_cell[cell] = name
                    landmarks.append(
                        {
                            "id": f"{cid}-{len(landmarks) + 1:04d}",
                            "name": name,
                            "category_id": cid,
                            "category": label,
                            "amap_type": t or None,
                            "address": p.get("address"),
                            "lat": float(p["lat"]),
                            "lng": float(p["lng"]),
                        }
                    )
                time.sleep(RATE_LIMIT_S)
            if total_requests % 10 == 0:
                print(f"  ...{total_requests} req, {len(landmarks)} landmarks", flush=True)

    doc = {
        "version": 1,
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "amap place/text (city=021) · 分类词条批量检索",
        "categories": [
            {"id": c["id"], "label": c["label"], "dayparts": c["dayparts"]}
            for c in CATEGORIES
        ],
        "landmarks": landmarks,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)

    # 按分类统计
    from collections import Counter

    cnt = Counter(l["category_id"] for l in landmarks)
    print(f"\nDONE: {len(landmarks)} landmarks, {total_requests} requests")
    for cid, n in sorted(cnt.items()):
        print(f"  {cid:<12} {n}")
    print(f"OUT: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
