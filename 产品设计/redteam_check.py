#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
红队回归校验器 —— 把「研学SOP与交付质量保障体系」的断言落成代码。
不依赖第三方库，仅用标准库即可运行。

用法:
  python redteam_check.py --case RT-02 --output agent_out.json
  python redteam_check.py --selftest
退出码 0 = 通过; 非0 = 门禁失败。
"""

import argparse
import json
import sys
from urllib.parse import urlparse

# ── 6 色海派 palette（样例 hex，可在「2.5D视图产品设计」锁定）──
PALETTE = {
    "墨":   "#20201E",
    "赭石": "#9C6B3F",
    "青灰": "#6E7E8C",
    "米白": "#EFE9DC",
    "朱":   "#B5341F",
    "宣纸": "#F7F2E7",
}
ALLOWED_COLORS = set(PALETTE.values())

# 契约必填顶层字段
REQUIRED_TOP = ["intent", "theme", "logic_line", "aesthetic",
                "scenario", "why_visit", "sources", "blocks"]
# 事实类字段：必须带 source
FACT_FIELDS = {"fact", "event", "figure", "address", "era", "year", "date"}

VIOLATIONS = []


def _walk(obj, path="$"):
    """生成 (path, key, value) 遍历叶节点。"""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk(v, f"{path}[{i}]")
    else:
        # 叶子：用父路径的最后一段作为 key 近似
        yield path, path.split(".")[-1].split("[")[0], obj


def check_contract(obj):
    """A1: 契约完整。"""
    for f in REQUIRED_TOP:
        if f not in obj or obj[f] in (None, "", [], {}):
            VIOLATIONS.append(f"A1 契约缺失字段: {f}")


def check_sources(obj):
    """A2: 来源可溯 —— 所有 source 字段非空且为 http(s)。"""
    found = False
    for path, key, val in _walk(obj):
        if key == "source":
            found = True
            if not isinstance(val, str) or not val.strip():
                VIOLATIONS.append(f"A2 source 为空: {path}")
            else:
                p = urlparse(val)
                if p.scheme not in ("http", "https"):
                    VIOLATIONS.append(f"A2 source 非 http(s): {path} = {val}")
    if not found:
        VIOLATIONS.append("A2 全文档无 source 字段")


def check_no_fabrication(obj):
    """A3: 零编造 —— 事实类字段须带 source。"""
    if not isinstance(obj, dict):
        return
    # 只查含 fact 字段的 dict 节点
    def rec(node):
        if isinstance(node, dict):
            if any(k in FACT_FIELDS for k in node):
                if "source" not in node or not node.get("source"):
                    VIOLATIONS.append(
                        f"A3 事实字段缺 source: 节点含 {set(node)&FACT_FIELDS}")
            for v in node.values():
                rec(v)
        elif isinstance(node, list):
            for v in node:
                rec(v)
    rec(obj)


def check_palette(obj):
    """A4: palette 合规。"""
    for path, key, val in _walk(obj):
        if key.lower() == "color" and isinstance(val, str):
            if val not in ALLOWED_COLORS:
                VIOLATIONS.append(f"A4 越界色值: {path} = {val}")


def check_five(obj):
    """A5: 5 要素齐。"""
    for f in ["theme", "logic_line", "aesthetic", "scenario", "why_visit"]:
        if f not in obj or not obj.get(f):
            VIOLATIONS.append(f"A5 缺失要素: {f}")


def check_slots(obj):
    """A6: 槽位显式（警告级）。"""
    if "persona" not in obj:
        VIOLATIONS.append("A6[warn] 未声明 persona 槽位")


def run_all(obj):
    VIOLATIONS.clear()
    check_contract(obj)
    check_sources(obj)
    check_no_fabrication(obj)
    check_palette(obj)
    check_five(obj)
    check_slots(obj)
    return list(VIOLATIONS)


# ── 自测样例 ──────────────────────────────────────────────
PASS_SAMPLE = {
    "intent": "教师课堂讲石库门红色历史",
    "theme": "石库门里的觉醒",
    "logic_line": "从空间到人物到事件",
    "aesthetic": {"tone": "克制有温度", "color": "#20201E"},
    "scenario": "初中历史一课",
    "why_visit": "学生能站在原地理解历史",
    "persona": {"人群": "教师"},
    "sources": [{"name": "上海图书馆", "source": "https://data1.library.sh.cn/red/xxx"}],
    "blocks": [{
        "type": "manual",
        "nodes": [{
            "title": "中共一大会址",
            "fact": "1921年7月召开",
            "address": "兴业路76号",
            "source": "https://data1.library.sh.cn/red/xxx"
        }]
    }]
}

FAIL_SAMPLE = {
    "intent": "x", "theme": "", "logic_line": "", "aesthetic": "",
    "scenario": "", "why_visit": "", "sources": [],
    "blocks": [{"type": "route", "nodes": [
        {"title": "某址", "fact": "1870年发生大事", "address": "某路1号"}
    ]}]
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case")
    ap.add_argument("--output")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        v1 = run_all(PASS_SAMPLE)
        v2 = run_all(FAIL_SAMPLE)
        print(f"[selftest] PASS样例 违规数={len(v1)} -> {'OK' if not v1 else 'FAIL'}")
        for x in v1:
            print("   ", x)
        print(f"[selftest] FAIL样例 违规数={len(v2)} -> {'拦截正确' if v2 else '未拦截!'}")
        for x in v2:
            print("   ", x)
        sys.exit(0 if (not v1 and v2) else 1)

    if not args.output:
        print("需 --output 或 --selftest")
        sys.exit(2)
    with open(args.output, encoding="utf-8") as f:
        obj = json.load(f)
    v = run_all(obj)
    print(f"用例 {args.case or '?'} 违规数={len(v)}")
    for x in v:
        print("  -", x)
    sys.exit(1 if v else 0)


if __name__ == "__main__":
    main()
