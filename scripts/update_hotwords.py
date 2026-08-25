#!/usr/bin/env python3
"""Publish L3 Shanghai hotwords (Tuesday weekly).

Usage:
  python scripts/update_hotwords.py
  python scripts/update_hotwords.py --inbox content/hotwords/inbox/week.json
  python scripts/update_hotwords.py --validate-only
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOT_DIR = ROOT / "content" / "hotwords"
LATEST = HOT_DIR / "latest.json"
ARCHIVE = HOT_DIR / "archive"
INBOX_DIR = HOT_DIR / "inbox"
DEFAULT_INBOX = INBOX_DIR / "week.json"

TERM_MAX = 24
MIN_ENTRIES = 8


def iso_week(d: date | None = None) -> str:
    d = d or date.today()
    return d.strftime("%G-W%V")


def _validate(data: dict) -> list[str]:
    errs: list[str] = []
    if not isinstance(data.get("week"), str) or not re.match(
        r"^\d{4}-W\d{2}$", data["week"]
    ):
        errs.append("week 必须为 ISO 格式 YYYY-Www")
    entries = data.get("entries")
    if not isinstance(entries, list) or len(entries) < MIN_ENTRIES:
        errs.append(f"entries 至少 {MIN_ENTRIES} 条")
        return errs
    ids: set[str] = set()
    for i, e in enumerate(entries):
        if not isinstance(e, dict):
            errs.append(f"entries[{i}] 非对象")
            continue
        eid = str(e.get("id") or "").strip()
        term = str(e.get("term") or "").strip()
        places = e.get("places")
        if not eid:
            errs.append(f"entries[{i}].id 缺失")
        elif eid in ids:
            errs.append(f"重复 id: {eid}")
        else:
            ids.add(eid)
        if not term or len(term) > TERM_MAX:
            errs.append(f"{eid or i}: term 长度 1–{TERM_MAX}")
        if not isinstance(places, list) or not places:
            errs.append(f"{eid or i}: places 不能为空")
        try:
            heat = float(e.get("heat"))
            if not 0 <= heat <= 1:
                errs.append(f"{eid or i}: heat 需在 0–1")
        except (TypeError, ValueError):
            errs.append(f"{eid or i}: heat 无效")
        hint = str(e.get("hint") or "")
        if not re.search(r"史实|开放|非史|不作史|不可当|馆藏", hint):
            errs.append(f"{eid or i}: hint 须提示不可作史实/开放时间")
    # attraction bias: at least half entries should mention a concrete place
    concrete = 0
    generic = {"上海", "徐汇", "静安", "虹口", "黄浦", "魔都"}
    for e in entries:
        if not isinstance(e, dict):
            continue
        pls = [str(p) for p in (e.get("places") or [])]
        if any(p not in generic for p in pls):
            concrete += 1
    if concrete < max(1, len(entries) // 2):
        errs.append("景点优先：超过一半条目应挂具体景点/路名")
    return errs


def _load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("根节点必须是对象")
    return data


def main() -> int:
    ap = argparse.ArgumentParser(description="Publish L3 hotwords index")
    ap.add_argument("--inbox", type=Path, default=None, help="inbox JSON path")
    ap.add_argument(
        "--validate-only",
        action="store_true",
        help="only validate latest.json or inbox",
    )
    ap.add_argument(
        "--week",
        type=str,
        default=None,
        help="override week label (YYYY-Www)",
    )
    args = ap.parse_args()

    inbox = args.inbox
    if inbox is None and DEFAULT_INBOX.exists():
        inbox = DEFAULT_INBOX

    if inbox is not None:
        src = inbox
    else:
        src = LATEST

    if not src.exists():
        print(f"missing: {src}", file=sys.stderr)
        print("先按 prompts/collect_hotwords_weekly.txt 采集到 inbox。", file=sys.stderr)
        return 2

    data = _load_json(src)
    if args.week:
        data["week"] = args.week
    data.setdefault("week", iso_week())
    data.setdefault("updated_at", date.today().isoformat())
    data.setdefault("source", "xiaohongshu_weekly")

    errs = _validate(data)
    if errs:
        print("VALIDATION FAILED:", file=sys.stderr)
        for e in errs:
            print(f"  - {e}", file=sys.stderr)
        return 1

    if args.validate_only:
        print(f"OK {src} week={data['week']} entries={len(data['entries'])}")
        return 0

    HOT_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    INBOX_DIR.mkdir(parents=True, exist_ok=True)

    # archive previous latest
    if LATEST.exists():
        prev = _load_json(LATEST)
        prev_week = str(prev.get("week") or "unknown")
        arch = ARCHIVE / f"{prev_week}.json"
        if prev_week != data["week"] or not arch.exists():
            shutil.copy2(LATEST, arch)

    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    LATEST.write_text(text, encoding="utf-8")
    # also archive this week
    (ARCHIVE / f"{data['week']}.json").write_text(text, encoding="utf-8")

    print(f"published {LATEST}")
    print(f"week={data['week']} entries={len(data['entries'])}")
    print("Tuesday cron tip: run this after Agent fills inbox/week.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
