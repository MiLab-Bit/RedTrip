"""数据源健康口径：注册、探测成功与快照落盘不可混为一谈。"""

from redtrip_library.providers import health_probe


def test_unprobed_live_providers_are_not_ready():
    report = health_probe()
    live = [provider for provider in report["providers"] if provider["mode"] == "live"]

    assert len(live) == 2
    assert all(not provider["ready"] for provider in live)
    assert report["live_ready"] == 0


def test_only_successfully_probed_live_provider_is_ready():
    report = health_probe({"slc": True, "souyun": False})
    by_id = {provider["id"]: provider for provider in report["providers"]}

    assert by_id["slc"]["ready"] is True
    assert by_id["souyun"]["ready"] is False
    assert report["live_ready"] == 1
    assert report["ingested"] == report["snapshot_ingested"] + 1
