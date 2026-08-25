"""Fetch OSM footprints for Wukang corridor into content/fixtures."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "library-client"))

from redtrip_library.osm import fetch_building_footprints  # noqa: E402

# Approx Wukang / Huashan corridor covering whitelist buris
SOUTH, WEST, NORTH, EAST = 31.2085, 121.4405, 31.2185, 121.4525


def main() -> int:
    data = fetch_building_footprints(
        south=SOUTH, west=WEST, north=NORTH, east=EAST, limit=120
    )
    out = ROOT / "content" / "fixtures" / "osm-wukang.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
        f.write("\n")
    print("count", data.get("count"), "error", data.get("error"))
    print("wrote", out)
    return 0 if data.get("count") else 1


if __name__ == "__main__":
    raise SystemExit(main())
