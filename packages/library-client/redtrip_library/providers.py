"""多数据源接入注册表与适配层（对应《数据源接入方案》§3–§4）。

设计原则（与方案一致）：
- 不改架构，只扩注册表 + 适配层；复用 SlcClient.call / EvidencePack 溯源结构。
- 每源可溯：进入正文的 partner 数据必须带 source.dataset=机构名 + record_id。
- 双通道：live（有 webapi 端点，走 call）与 snapshot（批量/关联数据，本地索引）。
- 降级诚实：某源 404/空 → 该层进 gaps，不编造。

本模块只依赖标准库 + 本地 content/partner/<id>.json 快照索引；不反向依赖 curator，
避免包间环。evidence.py 负责把本模块产出的裸记录包成 IdentityLayer。

注：绝大多数 partner 为 snapshot 通道，真实数据需机构授权/批量下载后落到
content/partner/<id>.json 才可被取证。未落盘时 gather_partner_evidence 如实返回 gaps，
确保「我们接入的数据」与代码 PROVIDERS 一一对应、经得起核查。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# RedTrip/content/partner —— snapshot 通道的本地索引目录
_PARTNER_DIR = Path(__file__).resolve().parents[3] / "content" / "partner"


@dataclass(frozen=True)
class ProviderSpec:
    id: str
    name: str
    mode: str                       # live | snapshot | pending
    join_key: tuple[str, ...]       # 挂在哪个枢纽：人名 / 地名 / buri / uri
    enrich: tuple[str, ...]         # 丰富维度：building/event/person/image/video/geoname/poem/literature
    priority: str = "P3"            # P0..P3 / 待定
    city: str | None = None         # 机构所在城市 key（None=全国/跨城）
    endpoints: tuple[str, ...] = field(default_factory=tuple)  # live 通道的 endpoint id
    index_table: str | None = None  # snapshot 通道对应的本地索引表（content/partner/<id>.json）
    note: str = ""


# ── §3 数据源注册表（28 家，含 3 家待定标注）─────────────────────────────────
PROVIDERS: dict[str, ProviderSpec] = {
    "slc": ProviderSpec(
        id="slc", name="上海图书馆", mode="live",
        join_key=("buri", "uri", "pname", "geo"),
        enrich=("building", "event", "person", "road", "era", "geoname"),
        priority="P0", city="shanghai",
        endpoints=("building_detail", "event_list", "persons_list", "geonames_list", "road_list"),
        note="平台聚合 28 家数据的总入口（data1.library.sh.cn）",
    ),
    "souyun": ProviderSpec(
        id="souyun", name="广州搜韵", mode="live",
        join_key=("地名", "人名"), enrich=("poem", "person"), priority="P0",
        city="guangzhou", endpoints=("souyun_poem", "souyun_couplet", "souyun_rhyme"),
        note="110 万诗词 / 300 万对仗 / 7.5 万人物（已接 poem，扩 couplet/rhyme）",
    ),
    "cbdb": ProviderSpec(
        id="cbdb", name="CBDB 中国历代人物传记", mode="snapshot",
        join_key=("人名",), enrich=("person",), priority="P1", city=None,
        index_table="content/partner/cbdb.json",
        note="52 万人物传记，结构化、join 成本最低",
    ),
    "gqbks": ProviderSpec(
        id="gqbks", name="全国报刊索引", mode="snapshot",
        join_key=("人名", "事件"), enrich=("event", "person", "image"), priority="P1",
        index_table="content/partner/gqbks.json",
        note="晚清/民国期刊、图库、报纸",
    ),
    "suzhou_lib": ProviderSpec(
        id="suzhou_lib", name="苏州图书馆", mode="snapshot",
        join_key=("人名",), enrich=("person",), priority="P1", city="suzhou",
        index_table="content/partner/suzhou_lib.json", note="苏州人物 1899 条 + 图 634",
    ),
    "suzhou_culture": ProviderSpec(
        id="suzhou_culture", name="苏州市公共文化中心", mode="snapshot",
        join_key=("人名",), enrich=("person", "image"), priority="P1", city="suzhou",
        index_table="content/partner/suzhou_culture.json", note="苏州名人 448 + 桃花坞年画",
    ),
    "nanjing_lib": ProviderSpec(
        id="nanjing_lib", name="南京图书馆", mode="snapshot",
        join_key=("人名", "事件"), enrich=("image", "person", "event"), priority="P1",
        city="nanjing", index_table="content/partner/nanjing_lib.json",
        note="近代文献图像库/抗战图库/百年人物",
    ),
    "jiaxing_lib": ProviderSpec(
        id="jiaxing_lib", name="嘉兴市图书馆", mode="snapshot",
        join_key=("事件", "人名"), enrich=("event", "person", "image"), priority="P1",
        city="jiaxing", index_table="content/partner/jiaxing_lib.json",
        note="南湖会议 128 篇/传记 538/墨迹 64（红色主题）",
    ),
    "yangzhou_lib": ProviderSpec(
        id="yangzhou_lib", name="扬州市图书馆", mode="snapshot",
        join_key=("人名",), enrich=("person",), priority="P2", city="yangzhou",
        index_table="content/partner/yangzhou_lib.json", note="扬州院士 102 位",
    ),
    "fudan_lib": ProviderSpec(
        id="fudan_lib", name="复旦大学图书馆", mode="snapshot",
        join_key=("人名",), enrich=("poem", "person"), priority="P2", city="shanghai",
        index_table="content/partner/fudan_lib.json", note="南社诗笺 92/诗文 410/作者 40",
    ),
    "songqingling": ProviderSpec(
        id="songqingling", name="上海宋庆龄研究会", mode="snapshot",
        join_key=("人名",), enrich=("person",), priority="P2", city="shanghai",
        index_table="content/partner/songqingling.json", note="宋庆龄著作/函电/档案/报刊",
    ),
    "taofen": ProviderSpec(
        id="taofen", name="上海韬奋纪念馆", mode="snapshot",
        join_key=("人名",), enrich=("person",), priority="P2", city="shanghai",
        index_table="content/partner/taofen.json", note="邹韬奋生平/年谱/馆藏书目",
    ),
    "zhejiang_lib": ProviderSpec(
        id="zhejiang_lib", name="浙江图书馆", mode="snapshot",
        join_key=("图像",), enrich=("image",), priority="P2", city="hangzhou",
        index_table="content/partner/zhejiang_lib.json", note="通典雕版图 500/雕版专题片 11",
    ),
    "shenzhen_lib": ProviderSpec(
        id="shenzhen_lib", name="深圳图书馆", mode="snapshot",
        join_key=("地点",), enrich=("building", "image", "video"), priority="P2",
        city="shenzhen", index_table="content/partner/shenzhen_lib.json",
        note="城市雕塑 41 + 图 1052/记忆视频 159",
    ),
    "nantong_lib": ProviderSpec(
        id="nantong_lib", name="南通市图书馆", mode="snapshot",
        join_key=("地名",), enrich=("geoname", "image", "video"), priority="P2",
        city="nantong", index_table="content/partner/nantong_lib.json", note="古镇老街图文 9044",
    ),
    "anhui_lib": ProviderSpec(
        id="anhui_lib", name="安徽省图书馆", mode="snapshot",
        join_key=("视频",), enrich=("video",), priority="P3", city="hefei",
        index_table="content/partner/anhui_lib.json", note="非遗/古建筑专题片 330 + 微视频",
    ),
    "hangya": ProviderSpec(
        id="hangya", name="杭州弘雅科技", mode="snapshot",
        join_key=("人名", "图像"), enrich=("image", "person"), priority="P3",
        city="hangzhou", index_table="content/partner/hangya.json",
        note="美术高清图 17 万/艺术家 1.3 万",
    ),
    "cadal": ProviderSpec(
        id="cadal", name="CADAL", mode="snapshot",
        join_key=(), enrich=("literature",), priority="P3", city=None,
        index_table="content/partner/cadal.json", note="用户行为 4088 万条（低策展价值）",
    ),
    "jingan": ProviderSpec(
        id="jingan", name="静安区图书馆", mode="snapshot",
        join_key=("视频",), enrich=("video", "geoname"), priority="P3", city="shanghai",
        index_table="content/partner/jingan.json", note="民俗专题片（合东方社区信息苑）",
    ),
    "minhang": ProviderSpec(
        id="minhang", name="闵行区图书馆", mode="snapshot",
        join_key=("视频",), enrich=("video", "geoname"), priority="P3", city="shanghai",
        index_table="content/partner/minhang.json", note="民俗专题片",
    ),
    "jiading": ProviderSpec(
        id="jiading", name="嘉定区图书馆", mode="snapshot",
        join_key=("视频",), enrich=("video", "geoname"), priority="P3", city="shanghai",
        index_table="content/partner/jiading.json", note="民俗专题片",
    ),
    "jinshan": ProviderSpec(
        id="jinshan", name="金山区图书馆", mode="snapshot",
        join_key=("视频",), enrich=("video", "geoname"), priority="P3", city="shanghai",
        index_table="content/partner/jinshan.json", note="民俗专题片",
    ),
    "fengxian": ProviderSpec(
        id="fengxian", name="奉贤区图书馆", mode="snapshot",
        join_key=("视频",), enrich=("video", "geoname"), priority="P3", city="shanghai",
        index_table="content/partner/fengxian.json", note="民俗专题片",
    ),
    "chongming": ProviderSpec(
        id="chongming", name="崇明区图书馆", mode="snapshot",
        join_key=("视频",), enrich=("video", "geoname"), priority="P3", city="shanghai",
        index_table="content/partner/chongming.json", note="民俗专题片",
    ),
    "dongfang": ProviderSpec(
        id="dongfang", name="东方社区信息苑", mode="snapshot",
        join_key=("视频",), enrich=("video",), priority="P3", city="shanghai",
        index_table="content/partner/dongfang.json", note="民俗专题片",
    ),
    # ── 待定（方案 §6：需官方《数据合作单位》清单核对）──
    "ecnu": ProviderSpec(
        id="ecnu", name="华东师范大学图书馆", mode="pending",
        join_key=(), enrich=(), priority="待定", city="shanghai", note="待确认合作范围",
    ),
    "ruc": ProviderSpec(
        id="ruc", name="中国人民大学图书馆", mode="pending",
        join_key=(), enrich=(), priority="待定", city=None, note="待确认合作范围",
    ),
    "shanghai_open": ProviderSpec(
        id="shanghai_open", name="上海市公共数据开放平台", mode="pending",
        join_key=(), enrich=(), priority="待定", city="shanghai",
        note="政府开放数据，建议单列确认",
    ),
}


# ── 归一化模板：raw 记录 → IdentityLayer 裸结构（kind/label/claim/source）───────
# 各 enrich 维度从原始记录里挑字段拼 claim。无真实数据时为占位逻辑，数据落盘即生效。
_ENRICH_CLAIM_TMPL: dict[str, str] = {
    "building": "（{name}）{type}：{desc}",
    "event": "（{name}）{era}：{desc}",
    "person": "（{name}）{role}：{desc}",
    "image": "影像：{name}（{type}）",
    "video": "影像：{name}（{type}）",
    "geoname": "地名：{name}——{desc}",
    "poem": "诗句：{name}（{author}）",
    "literature": "文献：{name}",
}


def _pick(rec: dict[str, Any], *keys: str) -> str:
    for k in keys:
        v = rec.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def normalize_record(rec: dict[str, Any], spec: ProviderSpec) -> list[dict[str, Any]]:
    """把一条 snapshot 原始记录按 provider 的 enrich 维度归一化为 IdentityLayer 裸结构。

    返回 list（一个记录可能贡献多个维度的 layer）。dataset 固定为机构名，保证可溯。
    """
    name = _pick(rec, "name", "title", "label", "姓名", "题名") or spec.name
    out: list[dict[str, Any]] = []
    for dim in spec.enrich:
        claim = _ENRICH_CLAIM_TMPL.get(dim, "{name}").format(
            name=name,
            type=_pick(rec, "type", "类别", "体裁") or "",
            era=_pick(rec, "era", "年代", "时间") or "",
            role=_pick(rec, "role", "身份", "职务") or "",
            author=_pick(rec, "author", "作者") or "",
            desc=_pick(rec, "desc", "description", "简介", "说明") or "",
        )
        rid = _pick(rec, "id", "record_id", "uri") or f"{spec.id}:{name}"
        out.append({
            "kind": dim,
            "label": name,
            "claim": claim,
            "source": {"dataset": spec.name, "record_id": rid},
        })
    return out


def load_snapshot(spec: ProviderSpec) -> list[dict[str, Any]] | None:
    """读取 provider 的本地 snapshot 索引。未落盘返回 None（调用方据实进 gaps）。"""
    if spec.mode != "snapshot" or not spec.index_table:
        return None
    p = _PARTNER_DIR.parent.parent / spec.index_table if spec.index_table.startswith("content/") \
        else _PARTNER_DIR / spec.index_table
    if not p.exists():
        return None
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None
    if isinstance(d, list):
        return d
    if isinstance(d, dict):
        for k in ("records", "items", "data", "persons"):
            if isinstance(d.get(k), list):
                return d[k]
    return None


def gather_partner_evidence(
    intent_city: str | None,
    *,
    limit: int = 6,
    priority_le: str = "P3",
) -> tuple[list[dict[str, Any]], list[str], list[dict[str, str]]]:
    """按城市 + 优先级收集已落盘 partner 的归一化 layer（裸结构）。

    返回 (layers, sources_used, gaps)。未落盘或 pending 的源进 gaps，不编造。
    视频类（video）按方案 §3 注：只作 POI 多媒体层，不进 claim——此处仍归一化，
    但 evidence 调用方可选择仅作附件。
    """
    layers: list[dict[str, Any]] = []
    sources_used: list[str] = []
    gaps: list[dict[str, str]] = []

    _PRI = {"P0": 0, "P1": 1, "P2": 2, "P3": 3, "待定": 9}
    prio_cap = _PRI.get(priority_le, 3)

    for spec in PROVIDERS.values():
        if spec.mode == "pending":
            gaps.append({"subject": spec.name, "note": "待确认合作范围（未接入）"})
            continue
        if spec.city not in (intent_city, None):
            continue
        if _PRI.get(spec.priority, 9) > prio_cap:
            continue
        recs = load_snapshot(spec)
        if not recs:
            gaps.append({"subject": spec.name, "note": "snapshot 未落盘（授权/批量数据待补）"})
            continue
        for rec in recs[:limit]:
            for layer in normalize_record(rec, spec):
                layers.append(layer)
        sources_used.append(spec.name)
    return layers, sources_used, gaps


def health_probe(
    live_results: dict[str, bool] | None = None,
) -> dict[str, Any]:
    """返回各 provider 的真实可用性矩阵。

    ``live_results`` 只接受本次运行中实际 HTTP probe 的结果；未 probe 的 live
    provider 保持 ``ready=false``。注册了 endpoint 不等于已成功接通。
    """
    live_results = live_results or {}
    matrix: list[dict[str, Any]] = []
    for spec in PROVIDERS.values():
        ready = False
        if spec.mode == "live":
            ready = bool(live_results.get(spec.id, False))
        elif spec.mode == "snapshot":
            ready = bool(load_snapshot(spec))
        matrix.append({
            "id": spec.id,
            "name": spec.name,
            "mode": spec.mode,
            "priority": spec.priority,
            "city": spec.city,
            "enrich": list(spec.enrich),
            "ready": ready,
            "readiness": (
                "ready"
                if ready
                else "probe_required"
                if spec.mode == "live"
                else "not_ingested"
                if spec.mode == "snapshot"
                else "pending_authorization"
            ),
            "note": spec.note,
        })
    live_ready = sum(
        1 for m in matrix if m["mode"] == "live" and m["ready"]
    )
    snapshot_ingested = sum(
        1 for m in matrix if m["mode"] == "snapshot" and m["ready"]
    )
    return {
        "total": len(matrix),
        "live": sum(1 for m in matrix if m["mode"] == "live"),
        "live_ready": live_ready,
        "snapshot_registered": sum(1 for m in matrix if m["mode"] == "snapshot"),
        "snapshot_ingested": snapshot_ingested,
        "ingested": live_ready + snapshot_ingested,
        "pending": sum(1 for m in matrix if m["mode"] == "pending"),
        "providers": matrix,
    }


def list_providers() -> list[dict[str, Any]]:
    return [{
        "id": s.id, "name": s.name, "mode": s.mode, "priority": s.priority,
        "city": s.city, "enrich": list(s.enrich), "join_key": list(s.join_key),
        "note": s.note,
    } for s in PROVIDERS.values()]
