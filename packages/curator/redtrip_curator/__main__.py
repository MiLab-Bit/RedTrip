"""CLI 入口：python -m redtrip_curator.book <envelope.json> [--output book.html].

也支持从 stdin 读取 JSON：
  cat envelope.json | python -m redtrip_curator.book --stdin --output book.html
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .book import render_book


def _load_envelope(path: str) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("envelope must be a JSON object")
    return data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render a RedTrip envelope to a book HTML")
    parser.add_argument("input", nargs="?", help="Path to envelope JSON file")
    parser.add_argument("--stdin", action="store_true", help="Read envelope JSON from stdin")
    parser.add_argument("--output", "-o", default="book.html", help="Output HTML path")
    args = parser.parse_args(argv)

    if args.stdin:
        envelope = json.load(sys.stdin)
    elif args.input:
        envelope = _load_envelope(args.input)
    else:
        parser.error("must provide input file or --stdin")

    if not isinstance(envelope, dict):
        parser.error("envelope must be a JSON object")

    html = render_book(envelope)
    Path(args.output).write_text(html, encoding="utf-8")
    print(f"book written to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
