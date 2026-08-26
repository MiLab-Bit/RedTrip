"""city 槽位安全：非法/穿越字符串必须回退 shanghai，不得拼进语料路径。"""
from redtrip_curator.cities import get_city
from redtrip_curator.intent import parse_intent


def test_malicious_city_falls_back_to_shanghai():
    for bad in (
        "../../../etc/passwd",
        "shanghai; rm -rf /",
        "suzhou\n\necho pwn",
        "../shanghai",
        "SHANGHAI",
        "",
    ):
        assert get_city(bad).key == "shanghai"
        intent = parse_intent({"city": bad, "scene": "外滩", "duration_min": 90})
        assert intent.city == "shanghai"


def test_known_cities_resolve():
    for key in ("suzhou", "hangzhou", "shanghai", "beijing"):
        assert get_city(key).key == key
        intent = parse_intent({"city": key, "scene": "外滩", "duration_min": 90})
        assert intent.city == key
