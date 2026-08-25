#!/usr/bin/env python3
"""S0 / W3 spike: probe Shanghai Library via library-client."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "library-client"))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")
os.environ.setdefault("PYTHONUTF8", "1")

from redtrip_library import SlcClient  # noqa: E402


def main() -> int:
    client = SlcClient()
    print("key_configured=", bool(client.key))
    probe = client.health_probe()
    print(json.dumps(probe, ensure_ascii=False, indent=2))

    uri = probe.get("sample_uri")
    if uri:
        print("\n--- building_detail ---")
        d = client.building_detail(uri)
        print(d.summary())
        if isinstance(d.data, dict):
            keys = list(d.data.keys())[:30]
            print("detail_top_keys=", keys)

        print("\n--- event_list(buri) ---")
        e = client.event_list(uri)
        print(e.summary())
        if e.ok:
            print("event_payload_type=", type(e.data).__name__)

    print("\n--- red_event_list (empty keyword probe) ---")
    re = client.red_event_list(keyword="")
    print(re.summary())

    ok = bool(probe.get("ok"))
    print("\nSPIKE_OK" if ok else "\nSPIKE_DEGRADED")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
