"""essay「路线零件」长散文：Gate 专属规则 + 书籍化渲染 回归测试。

覆盖：
- 良质 essay（同行者口吻 + 置信度感知 + 无 ##/A–F 标签）→ Gate 通过
- 渲染器把 essay block 渲染进 HTML / MDX / EPUB
- 负向：essay 出现 ## 标题 / A. 从现场进入 标签 / 你站在 导游腔 → 拦截
- 正向：essay 用「你若在此驻足」同行者口吻 → 不误杀
- 软告警：essay 浪漫化（烟火气）→ warning 不 blocker；C 级事实未带归属 → warning
"""
from redtrip_curator.book import render_book, render_book_epub_bytes, render_book_markdown
from redtrip_gate.engine import evaluate_envelope


def _stop(name, idx, meaning, transition):
    return {
        "name": name,
        "meaning": meaning,
        "transition_to_next": transition,
        "minutes": 20,
        "layers": [
            {
                "kind": "building",
                "label": f"{name}建筑",
                "claim": f"{name}的建筑事实",
                "source": {"dataset": "building_detail", "record_id": f"uri-b-{idx}"},
            },
            {
                "kind": "person",
                "label": f"{name}关联人物",
                "claim": f"{name}关联人物记载",
                "source": {"dataset": "building_detail.relation", "record_id": f"uri-p-{idx}"},
            },
        ],
        "raw_detail": {"address": "上海", "category": "historic", "poi_type": "历史古迹"},
        "pitfalls": {"open_hours": "9-17", "enterable": "可入", "need_reservation": "无需"},
        "geo": {"precision": "approximate", "coord_source": "amap"},
    }


# 三处地理/主题相距甚远：殖民公寓（徐汇衡复）/ 犹太避难（虹口提篮桥）/ 古刹与陵园（徐汇龙华）
ESSAYS = {
    1: {  # 武康大楼
        "title": "一艘停在街角的船，与它的乘客们",
        "body": (
            "武康路和淮海中路交成一个切角，一栋弧形的老公寓把人行道挤成一条窄缝。"
            "你若在此驻足，会先看见底层连续券廊被自行车和咖啡座占去一半，再抬头，"
            "才发现整栋楼像一艘船，船头正对十字路口。\n\n"
            "这栋楼 1924 年由邬达克设计，原名诺曼底公寓，是上海最早的自来水、"
            "暖气和电梯公寓之一。据地图标注，它所在街区在法租界时期被规划为"
            "高档住宅，但真正住在里面的，除了洋行职员，更多是买办、律师与他们的"
            "家眷——这些人很少出现在导游旗上，却是这栋楼能成立的前提。\n\n"
            "关于顶层某位寓公的具体生平，地方传闻称其曾在此藏匿友人，但无档案佐证，"
            "只能作为待核查的线索。如今底层商铺换过几轮，船还是那艘船，乘客早已不同。\n\n"
            "顺武康路往南，梧桐的影子会把你带向另一种「到来」——那里住过另一群"
            "被迫离开家乡的人。"
        ),
        "provenance": [
            {"text": "这栋楼 1924 年由邬达克设计，原名诺曼底公寓", "kind": "factual",
             "fact_uris": ["uri-b-1"], "grades": ["A"]},
            {"text": "据地图标注，它所在街区在法租界时期被规划为高档住宅",
             "kind": "factual", "fact_uris": ["amap:category:武康大楼"], "grades": ["C"]},
            {"text": "地方传闻称其曾在此藏匿友人，但无档案佐证", "kind": "connective",
             "fact_uris": [], "grades": []},
        ],
    },
    2: {  # 提篮桥 / 犹太难民纪念馆
        "title": "在「隔都」与城市之间",
        "body": (
            "过了苏州河往东北，提篮桥的街面陡然窄了，电线在头顶织成网。"
            "你抬头看，会注意到一幢不起眼的小楼门口钉着铜牌——摩西会堂，"
            "二战时这里曾接纳从欧洲逃来的犹太人。\n\n"
            "1943 年，日军在此划定「无国籍难民限定居住区」，约两万名犹太难民"
            "被要求住进提篮桥一带。这是一段被反复讲述又常被简化的历史："
            "他们与本地居民如何共用弄堂、彼此戒备又彼此依存，档案里留下的是"
            "租约与救济记录，而不是温情故事。\n\n"
            "今天纪念馆所在的建筑是否为当年原址，研究假设认为主体结构尚存，"
            "但内部已数次改建。你顺着长阳路走，会经过仍在使用的小商铺，"
            "居民未必知道脚下曾是一处世界记忆。\n\n"
            "从被记住的会堂，走向另一处「被记住」却更沉默的地点——龙华的塔影下，"
            "埋着另一群人的名字。"
        ),
        "provenance": [
            {"text": "1943 年，日军在此划定无国籍难民限定居住区", "kind": "factual",
             "fact_uris": ["uri-b-2"], "grades": ["A"]},
            {"text": "研究假设认为主体结构尚存，但内部已数次改建",
             "kind": "connective", "fact_uris": [], "grades": []},
        ],
    },
    3: {  # 龙华寺 / 龙华塔
        "title": "塔影下的两种纪念",
        "body": (
            "龙华路尽头，宋式木塔在香火气里立了一千多年。你若沿塔基走一圈，"
            "会发现塔身微微向东南倾，砖缝里长出草——这是活着的古建筑，不是展品。\n\n"
            "龙华塔相传始建于三国吴赤乌年间，现存结构为北宋重建；紧邻的龙华寺"
            "在历史上几毁几建，香火从未断。据地图标注，这一带在近代仍是上海"
            "县城外的郊野，寺与圩田、坟茔相邻。\n\n"
            "塔的东北不远，是龙华烈士陵园，纪念上世纪被处决的共产党人。"
            "同一片土地，一边是千年祈福，一边是世纪牺牲，两种「被记住」并置，"
            "却很少被放进同一条叙述里。谁的名字被刻进石碑，谁的沉默留在泥土，"
            "本身就是一个未完成的提问。\n\n"
            "从塔影回到路口，这一程关于「到来与记住」的线，到此收束——但城市的"
            "其他坐标，仍在等你重新走一遍。"
        ),
        "provenance": [
            {"text": "龙华塔相传始建于三国吴赤乌年间，现存结构为北宋重建",
             "kind": "factual", "fact_uris": ["uri-b-3"], "grades": ["A"]},
            {"text": "据地图标注，这一带在近代仍是上海县城外的郊野",
             "kind": "factual", "fact_uris": ["amap:category:龙华寺"], "grades": ["C"]},
        ],
    },
}


def _envelope(stops, essays=None, *, bad_essay=None):
    n = len(stops)
    blocks = [
        {"type": "story_card", "stop_order": i + 1, "title": f"卡片{i+1}",
         "body": "轻量带路正文。", "sources": [{"dataset": "slc", "record_id": f"y{i}"}]}
        for i in range(n)
    ]
    if essays:
        for so, ess in essays.items():
            blocks.append({"type": "essay", "stop_order": so,
                           "title": ess["title"], "body": ess["body"],
                           "provenance": ess["provenance"]})
    if bad_essay is not None:
        blocks.append({"type": "essay", "stop_order": 1,
                       "title": "坏样例", "body": bad_essay, "provenance": []})
    return {
        "intent": {"audience": "成人", "scene": "上海", "duration_min": 120,
                   "tone": "学术", "delivery": "导览", "companions": "朋友",
                   "assumptions": [], "daypart": "day"},
        "theme": "到来与记住：三处坐标",
        "logic_line": "并置论证三种「到来」",
        "aesthetic": "克制、留白",
        "scenario": "上海城市漫步",
        "why_visit": "读城市的到来与记住",
        "sources": [{"dataset": "slc", "record_id": "x"}],
        "blocks": blocks,
        "curator_note": "三处相距甚远的坐标，各自是不同人群到来的界面。",
        "route": {"duration_min": 120, "walk_meters_est": 8000, "stops": stops},
        "provenance": {
            "total_assertions": 2 * n, "aligned_assertions": 2 * n,
            "coverage_ratio": 1.0,
            "per_stop": [{"stop_index": i + 1,
                          "assertions": [{"aligned": True}, {"aligned": True}]}
                         for i in range(n)],
        },
        "curated_story": {
            "id": "essay-book", "theme": {"id": "t", "title": "到来与记住",
                                           "open_question": "？", "research_axes": [],
                                           "why_visit": "读城市的到来与记住",
                                           "estimated_duration_min": 120, "scope_note": ""},
            "thesis": "三处坐标各自是到来的界面。",
            "cast": [], "chapters": [
                {"id": f"ch-{i+1}", "index": i + 1, "title": f"第{i+1}站",
                 "hook": "", "narrativeRole": "Anchor", "stopId": i + 1,
                 "relationToPrevious": None, "evidenceIds": [], "walkingMinutes": 20,
                 "castRefs": []} for i in range(n)],
            "evidenceGraph": {"theme_id": "t", "clusters": [], "joins": [], "coverage": {}},
            "quality": {"evidence_layers": 2, "coverage_ratio": 1.0, "aligned_ratio": 1.0},
        },
    }


def _three_stops():
    return [
        _stop("武康大楼", 1, "认武康大楼：船形公寓与乘客", "从武康路走向长阳路"),
        _stop("提篮桥", 2, "认提篮桥：难民限定居住区", "从提篮桥走向龙华"),
        _stop("龙华寺", 3, "认龙华寺：塔影下的两种纪念", "从龙华走向下一处"),
        _stop("外滩源", 4, "认外滩源：江岸起点", "继续向前"),
        _stop("豫园", 5, "认豫园：老城厢", None),
    ]


def test_good_essays_pass_gate():
    env = _envelope(_three_stops(), essays=ESSAYS)
    v = evaluate_envelope(env)
    assert v.passed, v.blockers


def test_essay_renders_in_all_formats():
    env = _envelope(_three_stops(), essays=ESSAYS)
    html = render_book(env)
    assert "路线零件 · 长散文" in html
    assert "一艘停在街角的船" in html
    assert "在「隔都」与城市之间" in html
    assert "塔影下的两种纪念" in html
    md = render_book_markdown(env)
    assert "路线零件 · 长散文" in md
    data = render_book_epub_bytes(env)
    assert data[:2] == b"PK"


def test_essay_banned_structure_blocks():
    for bad in ("## 从现场进入\n这里曾经是……", "A. 从现场进入：你先看到",
                "B. 地方的时间叠层：此地曾经是", "你站在武康大楼门前，红砖浮起"):
        env = _envelope(_three_stops(), essays=ESSAYS, bad_essay=bad)
        v = evaluate_envelope(env)
        assert not v.passed, bad
        assert any("essay#1" in b for b in v.blockers), bad


def test_essay_companion_voice_not_blocked():
    """同行者口吻「你若在此驻足」应放行，不误杀。"""
    companion = "你若在此驻足，会先看见底层连续券廊被占去一半。"
    env = _envelope(_three_stops(), essays={
        1: {"title": "同行者", "body": companion + "\n\n其余正文。",
            "provenance": [{"text": companion, "kind": "connective",
                            "fact_uris": [], "grades": []}]},
    })
    v = evaluate_envelope(env)
    assert v.passed, v.blockers


def test_essay_nostalgia_warns_not_blocks():
    env = _envelope(_three_stops(), essays={
        1: {"title": "浪漫化", "body": "弄堂里满是烟火气，老上海的味道让人沉醉。\n\n其余。",
            "provenance": []},
    })
    v = evaluate_envelope(env)
    assert v.passed
    assert any("反怀旧" in w for w in v.warnings)


def test_essay_c_grade_without_attribution_warns():
    env = _envelope(_three_stops(), essays={
        1: {"title": "C级未归属", "body": "x", "provenance": [
            {"text": "这栋楼所在街区是高档住宅", "kind": "factual",
             "fact_uris": ["amap:category:武康大楼"], "grades": ["C"]},
        ]},
    })
    v = evaluate_envelope(env)
    assert v.passed
    assert any("置信度" in w for w in v.warnings)
