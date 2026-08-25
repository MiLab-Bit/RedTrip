#!/usr/bin/env python3
"""CI helper: warn/fail when L3 hotwords latest.json is stale.

Usage:
  python eval/check_hotwords_stale.py
  python eval/check_hotwords_stale.py --warn-days 14 --fail
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LATEST = ROOT / "content" / "hotwords" / "latest.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--warn-days", type=int, default=14)
    parser.add_argument("--fail", action="store_true", help="exit 1 when stale")
    args = parser.parse_args()

    if not LATEST.exists():
        msg = f"HOTWORDS_MISSING {LATEST}"
        print(msg)
        return 1 if args.fail else 0

    data = json.loads(LATEST.read_text(encoding="utf-8"))
    week = data.get("week")
    updated = data.get("updated_at")
    entries = data.get("entries") or []
    stale = True
    age_days = None

    if isinstance(updated, str):
        try:
            dt = datetime.strptime(updated[:10], "%Y-%m-%d").date()
            age_days = (date.today() - dt).days
            stale = age_days > args.warn_days
        except ValueError:
            stale = True

    ok = not stale and len(entries) >= 8
    print(
        f"hotwords week={week} updated={updated} entries={len(entries)} "
        f"age_days={age_days} stale={stale} ok={ok}"
    )
    if stale:
        print(f"WARN: hotwords older than {args.warn_days} days — run scripts/update_hotwords.py")
        if args.fail:
            return 1
    if len(entries) < 8:
        print("WARN: hotwords entries < 8")
        if args.fail:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
