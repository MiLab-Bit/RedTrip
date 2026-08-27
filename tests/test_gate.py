"""Gate（幻觉防线）单测：覆盖「未取证断言必拦」「禁用词」「缺字段」等核心承诺。

运行：.venv/Scripts/python.exe -m pytest tests/test_gate.py -q
"""
from redtrip_gate.engine import evaluate_envelope, FORBIDDEN_COPY


def _stop(name: str, idx: int) -> dict:
    return {
        "name": name,
        "meaning": f"认{name}：建筑与人的关系",
        "transition_to_next": None,
        "minutes": 15,
        "layers": [
            {
                "kind": "building",
                "label": "建筑",
                "claim": f"{name}的建筑事实",
                "source": {"dataset": "building_detail", "record_id": f"uri-b-{idx}"},
            },
            {
                "kind": "person",
                "label": "某人",
                "claim": f"{name}关联人物",
                "source": {"dataset": "building_detail.relation", "record_id": f"uri-p-{idx}"},
            },
        ],
        "raw_detail": {"address": "中山东一路", "category": "historic", "poi_type": "历史古迹"},
        "pitfalls": {"open_hours": "9-17", "enterable": "可入", "need_reservation": "无需"},
        "geo": {"precision": "approximate", "coord_source": "amap"},
    }


def _envelope(stops: list[dict]) -> dict:
    n = len(stops)
    return {
        "intent": {
            "audience": "家庭", "scene": "外滩", "duration_min": 60, "tone": "学术",
            "delivery": "导览", "companions": "朋友", "assumptions": [], "daypart": "day",
        },
        "theme": "同一张城市面孔",
        "logic_line": "并置论证",
        "aesthetic": "海派",
        "scenario": "外滩漫步",
        "why_visit": "读建筑",
        "sources": [{"dataset": "slc", "record_id": "x"}],
        "blocks": [
            {"type": "story_card", "title": "卡片", "body": "正文",
             "sources": [{"dataset": "slc", "record_id": "y"}]},
        ],
        "curator_note": "策展注",
        "route": {"duration_min": 60, "stops": stops},
        "provenance": {
            "total_assertions": 2 * n,
            "aligned_assertions": 2 * n,
            "coverage_ratio": 1.0,
            "per_stop": [
                {"stop_index": i + 1, "assertions": [{"aligned": True}, {"aligned": True}]}
                for i in range(n)
            ],
        },
    }


def test_clean_passes():
    v = evaluate_envelope(_envelope([_stop(f"外滩{i}", i) for i in range(5)]))
    assert v.passed, v.blockers


def test_missing_required_field_blocks():
    e = _envelope([_stop("外滩0", 0), _stop("外滩1", 1), _stop("外滩2", 2)])
    del e["theme"]
    v = evaluate_envelope(e)
    assert not v.passed
    assert any("theme" in b for b in v.blockers)


def test_unaligned_provenance_blocks():
    """G4：溯源覆盖率不足必须拦截（编造/无出处事实的兜底网）。"""
    e = _envelope([_stop("外滩0", 0), _stop("外滩1", 1), _stop("外滩2", 2)])
    e["provenance"]["aligned_assertions"] = 1
    e["provenance"]["coverage_ratio"] = 0.5
    v = evaluate_envelope(e)
    assert not v.passed
    assert any("G4" in b for b in v.blockers)


def test_fabricated_no_source_blocks():
    """事实断言没有 record_id（编造年份/人名无出处）→ Q2 拦截。"""
    e = _envelope([_stop("外滩0", 0), _stop("外滩1", 1), _stop("外滩2", 2)])
    e["route"]["stops"][0]["layers"][0]["source"] = {"dataset": "building_detail", "record_id": ""}
    v = evaluate_envelope(e)
    assert not v.passed
    assert any("Q2" in b for b in v.blockers)


def test_forbidden_copy_blocks():
    e = _envelope([_stop("外滩0", 0), _stop("外滩1", 1), _stop("外滩2", 2)])
    e["curator_note"] = "一键搞定攻略"
    v = evaluate_envelope(e)
    assert not v.passed
    assert any("Q8" in b for b in v.blockers)


def test_forbidden_copy_b1_cliche_blocks():
    """B1：Gemini 文学套话（如「融汇中西」「仿佛穿越回老上海」）必须被 Q8 拦截。"""
    # 选一个冗余字段塞入套话，验证 Gate 对所有叙述文本扫描生效
    e = _envelope([_stop("外滩0", 0), _stop("外滩1", 1), _stop("外滩2", 2)])
    e["logic_line"] = "这里融汇中西，仿佛穿越回老上海"
    v = evaluate_envelope(e)
    assert not v.passed
    assert any("Q8" in b and "融汇中西" in b for b in v.blockers)

    e2 = _envelope([_stop("外滩0", 0), _stop("外滩1", 1), _stop("外滩2", 2)])
    e2["theme"] = "古今交融的海派漫步"
    v2 = evaluate_envelope(e2)
    assert not v2.passed
    assert any("Q8" in b and "古今交融" in b for b in v2.blockers)


def test_second_person_reader_address_in_story_card_passes():
    """R-06：story_card 必须允许第二人称，不得被全局 Q8 误伤。"""
    for phrase in ("你站在中山东一路33号", "你脚下是英国领事馆", "你忽然明白所谓码头"):
        e = _envelope([_stop(f"外滩{i}", i) for i in range(5)])
        e["blocks"][0]["body"] = f"{phrase}，红砖立面浮起。"
        # 给每站补史实衔接，避免 R19 误伤
        for i, s in enumerate(e["route"]["stops"][:-1]):
            s["transition_to_next"] = f"下一站用人物与记载对照，而不是步行距离（自 {_stop(f'外滩{i}', i)['name']}）。"
        v = evaluate_envelope(e)
        assert v.passed, (phrase, v.blockers)


def test_second_person_terms_only_block_essay():
    """第二人称导游腔只在长散文 essay 门禁生效。"""
    required = (
        "你站在", "你脚下", "你忽然", "你此刻", "你离开",
        "你遇见", "你会先遇见", "你带走", "你眼前", "你带着",
    )
    leaked = [w for w in required if w in FORBIDDEN_COPY]
    assert not leaked, f"第二人称词不应出现在全局 FORBIDDEN_COPY: {leaked}"

    e = _envelope([_stop("外滩0", 0), _stop("外滩1", 1), _stop("外滩2", 2)])
    e["blocks"].append({
        "type": "essay",
        "stop_order": 1,
        "title": "长散文",
        "body": "你站在门口，等待历史开口。",
    })
    v = evaluate_envelope(e)
    assert not v.passed
    assert any("Q8[essay#1]" in b and "你站在" in b for b in v.blockers)
