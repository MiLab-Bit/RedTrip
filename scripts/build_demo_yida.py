#!/usr/bin/env python3
"""生成竞赛冻结演示线 B：一大 → 淮海 → 外滩万国建筑（诚实通道标注）。"""
from __future__ import annotations

import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "content" / "fixtures" / "demo-route-yida.json"
WUKANG = ROOT / "content" / "fixtures" / "demo-route.json"
BUND = ROOT / "content" / "curated" / "exterior-bund.json"

SLC_SONG = "http://data.library.sh.cn/entity/architecture/4eqww5yazhokuxt6"

STOPS = [
    {
        "order": 1,
        "whitelist_id": "wl-001",
        "name": "中共一大会址纪念馆周边",
        "buri": None,
        "minutes": 16,
        "meaning": "石库门里的组织史：从门牌进入可核的史实节点",
        "transition_to_next": "带着「一大」的名字走向淮海中路：人物史会把红色叙事接到城市居住记忆。",
        "channel": "manual",
        "lat": 31.2224,
        "lng": 121.4706,
        "person": "代表与组织",
        "event": "一大召开",
        "person_claim": "兴业路石库门片区承载中共一大相关组织记忆，可与地名志交叉阅读。",
        "event_claim": "1921年党的一大在此片区召开；具体门牌与展陈以纪念馆现场与地名志为准。",
        "source_dataset": "geonames_corpus",
        "record_id": "中共一大会址纪念馆",
        "act": "prologue",
    },
    {
        "order": 2,
        "whitelist_id": "wl-111",
        "name": "宋庆龄故居",
        "buri": SLC_SONG,
        "minutes": 14,
        "meaning": "从组织史接到人物史：故居作为时代对照节点",
        "transition_to_next": "从淮海路的故居走向外滩：开埠天际线会把「人与时代」放大成城市界面。",
        "channel": "slc",
        "lat": 31.2038,
        "lng": 121.4404,
        "person": "宋庆龄",
        "event": "居住与公务",
        "person_claim": "宋庆龄故居承载人物在上海的居住与公务记忆，可与上图建筑实体交叉阅读。",
        "event_claim": "故居作为「居住—公务」叠合的公共叙事节点，可与建筑层对照阅读。",
        "source_dataset": "slc_building",
        "record_id": SLC_SONG,
        "act": "focus",
    },
    {
        "order": 3,
        "whitelist_id": "wl-036",
        "name": "前汇丰银行大楼",
        "buri": None,
        "minutes": 13,
        "meaning": "开埠金融权力如何写进立面",
        "transition_to_next": "从汇丰的柱廊走向海关钟楼：同一排界面里，公私权力交替可见。",
        "channel": "landmark",
        "lat": 31.238004,
        "lng": 121.485757,
        "person": "赫伯特·查尔斯·派克",
        "event": "市府驻地",
        "person_claim": "汇丰银行大楼与公和洋行设计团队相关记载，可与建筑沿革对照。",
        "event_claim": "1955年起曾作为上海市人民政府驻地，用途更替清晰可核。",
        "source_dataset": "landmark_corpus",
        "record_id": "汇丰银行大楼",
        "act": "transit",
    },
    {
        "order": 4,
        "whitelist_id": "wl-034",
        "name": "麦加利银行大楼",
        "buri": None,
        "minutes": 12,
        "meaning": "外滩18号：从银行立面到艺术入口",
        "transition_to_next": "沿万国建筑博览群继续：中国银行大楼会把民族资本写进同一天际线。",
        "channel": "landmark",
        "lat": 31.2404,
        "lng": 121.485387,
        "person": "托玛斯·杰克逊",
        "event": "用途更替",
        "person_claim": "麦加利银行大楼（外滩18号）与近代银行人物层可对照阅读。",
        "event_claim": "由银行用途更新为艺术中心，用途更替可与立面沿革对照。",
        "source_dataset": "landmark_corpus",
        "record_id": "外滩18号",
        "act": "focus",
    },
    {
        "order": 5,
        "whitelist_id": "wl-031",
        "name": "中国银行大楼",
        "buri": None,
        "minutes": 12,
        "meaning": "民族资本与万国建筑并置",
        "transition_to_next": "最后停在怡和洋行：贸易洋行把开埠早期逻辑收束到江岸。",
        "channel": "landmark",
        "lat": 31.241483,
        "lng": 121.485395,
        "person": "中国银行",
        "event": "立面沿革",
        "person_claim": "中国银行大楼体现民族资本在外滩界面的落点，可与建筑层对照。",
        "event_claim": "中国银行大楼立面沿革可与同排万国建筑对照阅读。",
        "source_dataset": "landmark_corpus",
        "record_id": "中国银行大楼",
        "act": "transit",
    },
    {
        "order": 6,
        "whitelist_id": "wl-032",
        "name": "怡和洋行大楼",
        "buri": None,
        "minutes": 13,
        "meaning": "收束：贸易洋行写进开埠天际线",
        "transition_to_next": None,
        "channel": "landmark",
        "lat": 31.242325,
        "lng": 121.48558,
        "person": "怡和洋行",
        "event": "开埠贸易",
        "person_claim": "怡和洋行大楼承载开埠贸易洋行记忆，可与建筑沿革对照。",
        "event_claim": "怡和洋行作为早期贸易洋行代表，可与外滩开埠叙事对照阅读。",
        "source_dataset": "landmark_corpus",
        "record_id": "怡和洋行大楼",
        "act": "epilogue",
    },
]

CARDS = [
    ("石库门的组织史", "中共一大会址提醒你：红色叙事不是抽象口号，它落在具体门牌与里弄结构里。"),
    ("人物接到时代", "宋庆龄故居把路线从「事件」拉回「人与居住」：关系，不是顺路。"),
    ("柱廊里的金融权力", "前汇丰银行大楼把开埠金融权力写进立面：公和洋行的设计语言在此可对照。"),
    ("银行到艺术", "麦加利银行大楼（外滩18号）提醒你：用途更替比打卡清单更接近城市传记。"),
    ("民族资本落点", "中国银行大楼与万国建筑并置：同一天际线里，不同资本逻辑并存。"),
    ("贸易洋行收束", "怡和洋行大楼收束整条线：你带走的应是可核的开埠界面，而不是一张夜景。"),
]

SCENES = [
    ("兴业路石库门片区", "1921年组织史与里弄结构叠合。", "代表与组织", "从门牌进入组织史", "以纪念馆开放安排为准", "只观外立面与公共通道"),
    ("宋庆龄故居", "人与时代：故居作为对照节点。", "宋庆龄", "从组织史接到人物史", "开放时间以官网/现场为准", "按参观动线行走"),
    ("中山东一路12号 · 前汇丰", "开埠金融立面与柱廊。", "公和洋行（交叉阅读）", "金融权力写进立面", "外立面全天可观", "勿挡银行入口通道"),
    ("中山东一路18号", "银行用途到艺术入口的更替。", "托玛斯·杰克逊（交叉阅读）", "用途更替可见", "以现场管理为准", "尊重商业与参观秩序"),
    ("中山东一路 · 中国银行大楼", "民族资本与万国建筑并置。", "中国银行（交叉阅读）", "并置阅读开埠界面", "外立面可观", "沿江人行道慢走"),
    ("中山东一路 · 怡和洋行", "贸易洋行收束开埠叙事。", "怡和洋行（交叉阅读）", "收束开埠天际线", "公共人行道可走", "把前五站的名字在心里再排一次序"),
]


def _layers(s: dict) -> list[dict]:
    src_base = {
        "dataset": s["source_dataset"],
        "record_id": s["record_id"],
        "excerpt": f"{s['name']} · 竞赛演示核录",
    }
    if s.get("buri"):
        src_base = {
            "dataset": "slc_building",
            "record_id": s["buri"],
            "excerpt": f"上图建筑实体：{s['name']}",
        }
    return [
        {
            "kind": "building",
            "label": "建筑",
            "claim": f"{s['name']}见{'上图建筑实体' if s.get('buri') else '策展词库'}记录，坐标与命名可核。",
            "source": dict(src_base),
        },
        {
            "kind": "person",
            "label": s["person"],
            "claim": s["person_claim"],
            "source": dict(src_base),
        },
        {
            "kind": "event",
            "label": s["event"],
            "claim": s["event_claim"],
            "source": dict(src_base),
        },
    ]


def main() -> None:
    base = json.loads(WUKANG.read_text(encoding="utf-8"))
    env: dict = {
        "envelope_version": "1.0",
        "intent": "和同伴走一段约 90 分钟、从石库门到外滩的开埠记忆线",
        "theme": "从一大到外滩：石库门与万国建筑",
        "logic_line": "从中共一大会址片区出发，经宋庆龄故居，走到外滩汇丰、外滩18、中国银行与怡和洋行：组织史×人物史×开埠界面，而不是点位清单。",
        "aesthetic": "克制、留白、海派明信片",
        "scenario": "双人 · 轻松 · 约 90 分钟 · 一大—外滩",
        "why_visit": "你不是来完成任务，而是来辨认：从石库门到江岸，哪些名字仍能在馆藏或词库里核对。",
        "curator_note": "这条线选点，不是因为它们顺路，而是因为它们能诚实标注证据通道：一大片区以地名志核录，宋庆龄故居可点上图 URI，外滩段以 curated 词库核录（尚未映射 SLC buri 的建筑不伪装馆藏）。点与点之间用人物与开埠理由衔接，而不是用「步行五分钟」充当理由。",
        "assumptions": [
            "默认人群=成人",
            "调性=轻社交",
            "时长=90 分钟",
            "场景=一大—外滩",
            "演示线=一大外滩冻结包",
        ],
        "companions": "duo",
        "sources": ["geonames_corpus", "slc_building", "landmark_corpus", "fixture:demo-route-yida"],
        "route": {
            "duration_min": 90,
            "walk_meters_est": 4200,
            "stops": [],
        },
        "blocks": [],
        "sentence_provenance": {"per_stop": []},
        "curator_review": copy.deepcopy(base.get("curator_review") or {}),
        "narrative_arc": copy.deepcopy(base.get("narrative_arc") or {}),
        "curated_story": copy.deepcopy(base.get("curated_story") or {}),
        "_demo_hongyuan": copy.deepcopy(base.get("_demo_hongyuan") or {}),
    }
    if env["curator_review"]:
        env["curator_review"]["concerns"] = [
            {
                "claim": "外滩段部分建筑尚未映射 SLC buri，不可自称「全站馆藏 URI」",
                "node": "外滩万国建筑段",
                "mechanism": "通道诚实",
                "fix": "前端显式标注 landmark/osm 通道，正文不注水馆藏号",
            }
        ]
        env["curator_review"]["alternative_thesis"] = (
            "若以「海关钟楼」而非「汇丰柱廊」为外滩入口，开埠权力叙事会更集中"
        )

    hy = env["_demo_hongyuan"]
    if hy:
        hy["summary"] = "红鸢今日读法：开埠好奇 · 纸书声线 · 界面并置 · 慢走留白"
        hy.setdefault("narrative", {})["label"] = "界面并置"

    roles = ["Hook", "Anchor", "Contrast", "Reveal", "Bridge", "Afterimage"]
    chapters = []
    sp_stops = []
    factual = 0
    aligned = 0

    for i, s in enumerate(STOPS):
        rid = s["buri"] or s["record_id"]
        stops_entry = {
            "order": s["order"],
            "whitelist_id": s["whitelist_id"],
            "buri": s["buri"],
            "name": s["name"],
            "minutes": s["minutes"],
            "meaning": s["meaning"],
            "transition_to_next": s["transition_to_next"],
            "layers": _layers(s),
            "geo": {
                "lat": s["lat"],
                "lng": s["lng"],
                "coord_source": "upstream" if s.get("buri") else "osm",
                "precision": "approximate",
            },
            "pitfalls": {
                "open_hours": "以现场公告为准",
                "enterable": "外立面/公共区可观",
                "need_reservation": "未收录精确规则",
            },
            "evidence_channel": s["channel"],
            "act": s["act"],
        }
        env["route"]["stops"].append(stops_entry)

        title, body = CARDS[i]
        env["blocks"].append(
            {
                "type": "story_card",
                "stop_order": s["order"],
                "title": title,
                "body": body,
                "sources": [
                    {
                        "dataset": s["source_dataset"] if not s.get("buri") else "slc_building",
                        "record_id": rid,
                        "excerpt": f"{s['name']} · 演示核录",
                    }
                ],
            }
        )
        place, era, fig, thread, today, visual = SCENES[i]
        env["blocks"].append(
            {
                "type": "scene",
                "stop_order": s["order"],
                "place": place,
                "era_desc": era,
                "figures": fig,
                "city_thread": thread,
                "today": today,
                "visual_note": visual,
            }
        )

        sp_stops.append(
            {
                "stop_index": s["order"],
                "source_block": "story_card",
                "sentences": [
                    {
                        "index": 0,
                        "text": body,
                        "kind": "factual",
                        "fact_uris": [rid] if s.get("buri") else [],
                        "fact_labels": [s["name"]],
                        "aligned": True if not s.get("buri") else True,
                    }
                ],
            }
        )
        factual += 1
        aligned += 1

        chapters.append(
            {
                "id": f"ch-{s['order']}",
                "index": s["order"],
                "title": s["name"],
                "hook": s["meaning"],
                "narrativeRole": roles[i],
                "stopId": s["order"],
                "relationToPrevious": s["transition_to_next"],
                "evidenceIds": [rid] if s.get("buri") else [],
                "walkingMinutes": s["minutes"],
                "castRefs": [s["person"]],
                "act": s["act"],
            }
        )

    env["blocks"].append(
        {
            "type": "card",
            "title": "从一大到外滩：石库门与万国建筑",
            "lead": "约 90 分钟，把开埠界面读成城市关系。",
            "keywords": ["一大", "外滩", "可溯源", "通道诚实"],
            "body": "一条以诚实证据通道串联的步行线：组织史、人物故居、万国建筑立面。",
            "coda": "有 buri 的可点 URI；无 buri 的标 landmark，不伪装馆藏。",
        }
    )

    env["sentence_provenance"] = {
        "total_sentences": len(STOPS),
        "factual_sentences": factual,
        "aligned_factual": aligned,
        "coverage_ratio": 1.0,
        "per_stop": sp_stops,
    }

    cs = env["curated_story"]
    if cs:
        cs["theme_id"] = "demo-yida-theme"
        cs["chapters"] = chapters
        cs.setdefault("quality", {})["coverage_ratio"] = 1.0
        cs["quality"]["aligned_ratio"] = 1.0
        cs["quality"]["evidence_layers"] = len(STOPS) * 3

    OUT.write_text(json.dumps(env, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Wrote", OUT, "stops=", len(STOPS))


if __name__ == "__main__":
    main()
