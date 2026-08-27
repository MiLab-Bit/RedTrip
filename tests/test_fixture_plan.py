"""fixture_plan：从 envelope 重建 plan，不改站序。"""
import json
from pathlib import Path

from redtrip_curator.fixture_plan import plan_from_envelope


def test_plan_from_yida_fixture():
    root = Path(__file__).resolve().parents[1]
    path = root / "content" / "fixtures" / "demo-route-yida.json"
    env = json.loads(path.read_text(encoding="utf-8"))
    plan = plan_from_envelope(env)
    assert len(plan.stops) == 6
    orders = [s.order for s in plan.stops]
    assert orders == [1, 2, 3, 4, 5, 6]
    assert plan.stops[0].evidence.name.startswith("中共一")
    assert plan.stops[2].evidence.raw_detail  # 汇丰 landmark 详情
    assert "1923" in str(plan.stops[2].evidence.raw_detail.get("landmark_year_built"))
