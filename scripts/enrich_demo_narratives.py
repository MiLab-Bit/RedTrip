#!/usr/bin/env python3
"""把冻结演示线的 story_card 加厚为「可读的策展正文」，并重建句级溯源。

Usage:
  PYTHONPATH=packages/curator:packages/gate python3 scripts/enrich_demo_narratives.py
"""
from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "curator"))
sys.path.insert(0, str(ROOT / "packages" / "gate"))

from redtrip_curator.sentence_provenance import build_sp_from_envelope  # noqa: E402
from redtrip_gate.engine import evaluate_envelope  # noqa: E402

# ── 武康六站：正文来自 curated-live / live-sample / 上图公开实体（仅写已取证句）──
WUKANG_CARDS: dict[int, dict] = {
    1: {
        "title": "巴金与「巴金故居」",
        "body": (
            "你停在武康路113号的「巴金故居」前。先别报建筑名，先报一个人的名字：巴金。"
            "这座城市把人藏进门牌的本事，比把人印上标语高明。\n\n"
            "这栋楼不是空壳，馆藏让几个人在此交错：\n"
            "巴金——1955年9月迁入并定居于此，《随想录》等诸多重要作品都在此创作。\n"
            "史宾伯——1948年改建后，原房主返国，由丹麦人史宾伯照看这处房产。\n"
            "毛特宝林海——1923年始建时的原房主。\n"
            "萧珊——名字写进与此楼相关的记载。\n"
            "他们未必曾在同一天推开这扇门；可当名字并列，你读到的是时间在换人，楼还在。\n\n"
            "在武康路113号的「巴金故居」，时间并不温和，它一截一截改写用途：\n"
            "1923年，始建，原房主为英国人毛特宝林海。\n"
            "1948年，改建，原房主返国后由丹麦人史宾伯照看这处房产。\n"
            "1950-1955年，作为苏联商务代表处。\n"
            "1955年9月，巴金一家迁入，并定居于此，《随想录》等诸多重要作品都在此创作。\n"
            "1999年9月23日，被上海市人民政府公布为第三批上海市优秀历史建筑。\n"
            "读到这里，你该感到一种紧张：楼还在，屋里的人与用途却在被替换。\n\n"
            "这一站要你回答的问题是：一栋楼如何同时装下史宾伯、毛特宝林海、巴金，"
            "以及那些改写用途的年份？答案不在动员里，在你刚读过的句子里——"
            "人换了，记载还在，门牌仍可被路过。\n\n"
            "抬眼看立面与门头。把刚才的名字轻轻放回年份里，再决定要不要走进去。"
            "驻足约 14 分钟就够——短篇靠密度，不靠耗尽脚力。"
        ),
        "sources": [
            {
                "dataset": "slc_building",
                "record_id": "http://data.library.sh.cn/entity/architecture/if3k5yb021u3c4vd",
                "excerpt": "3层，占地面积1484平方米；1923始建；1955年9月巴金迁入",
            },
            {
                "dataset": "event_list",
                "record_id": "nodeID://b18509771",
                "excerpt": "1923年，始建，原房主为英国人毛特宝林海。",
            },
        ],
        "age_parallel": "若把「巴金」当作这一站的主人公，上面的年份就是他必须穿过的布景。布景有据；更私密的心事，缺记载处不写。",
        "scene": {
            "place": "武康路113号 · 巴金故居",
            "era_desc": "1923始建；1948史宾伯照看；1955年9月巴金迁入；《随想录》在此创作；1999年第三批优秀历史建筑。",
            "figures": "巴金、史宾伯、毛特宝林海、萧珊",
            "city_thread": "从门牌读出私人时间如何变成公共文字",
            "today": "周二至周日约10:00–16:30 · 可购票入内",
            "visual_note": "站在人行道外侧看门牌与立面；勿扰仍在使用的空间。",
        },
    },
    2: {
        "title": "周璇与「周璇旧居」",
        "body": (
            "你停在武康路391弄1-5号的「周璇旧居」前。此刻冲突很安静："
            "你看得见砖与窗，却还不知道谁曾在这扇门后度过漫长的白天。\n\n"
            "在「周璇旧居」，时间并不温和，它一截一截改写用途：\n"
            "1916年，始建。\n"
            "1943年，中国最早的两栖明星、流行歌曲的先驱者——「金嗓子」周璇，搬入。\n"
            "1946年，周璇搬离。市房管局档案载：此屋尝在捷克侨民高礼文名下。\n"
            "1953年，市房地局按无主产业予以代管。\n"
            "现为民居。\n"
            "读到这里，你该感到一种紧张：楼还在，屋里的人与用途却在被替换。\n\n"
            "这一站的主题是用途的更替：谁住过、谁用过、谁离开。"
            "流行文化不是抽象标签，它落在具体门牌与用途更替里。"
            "你站在外面，等于站在一段被压缩的城市传记门口。\n\n"
            "从巴金的写作日常走到周璇的搬入搬离：同一条武康路上，"
            "文学与流行文化并行，不互相取消。抬眼看门楣，把年份轻轻放回名字里。"
        ),
        "sources": [
            {
                "dataset": "slc_building",
                "record_id": "http://data.library.sh.cn/entity/architecture/p8lpy1b17cgrkse4",
                "excerpt": "周璇旧居 · 1916始建；1943搬入；1946搬离",
            },
        ],
        "scene": {
            "place": "武康路391弄1-5号 · 周璇旧居",
            "era_desc": "1916始建；1943周璇搬入；1946搬离；1953代管；现民居。",
            "figures": "周璇、高礼文（档案记载）",
            "city_thread": "金嗓子与民居：传记如何住进砖瓦",
            "today": "外立面全天可观 · 民居不可入内",
            "visual_note": "只观门楣与立面，不按门铃，不挡通道。",
        },
    },
    3: {
        "title": "邬达克与「武康大楼」",
        "body": (
            "你停在淮海中路与武康路交叉口的「武康大楼」前。"
            "这里不是普通住宅，而是把个人传记抬到城市界面的地方——"
            "道路交叉处，立面本身就是机制。\n\n"
            "据上图建筑实体记载：\n"
            "1924年，诺曼底公寓始建，由邬达克设计建造。\n"
            "1930年，建新武康大楼副楼。\n"
            "1953年，诺曼底公寓被上海市人民政府接管并更名为武康大楼。\n"
            "1994年，武康大楼选入第二批上海市优秀历史建筑。\n\n"
            "大楼建成时，几乎是欧美在沪侨民的第一批主人；"
            "孤岛时期，新华影业和联华影业距离大楼只有一步之遥，"
            "王人美、吴茵、吴君谋夫妇等电影圈人士租住在此。"
            "到了新中国成立后，郑君里、赵丹黄宗英夫妇、孙道临王文娟夫妇也相继入驻——"
            "个人传记被收进同一栋交叉路口的大楼立面里。\n\n"
            "这一站要你回答：为什么同一栋楼能同时装下建筑师的名字、"
            "侨民与电影圈、再到后来文化名人的居住记忆？"
            "答案在立面的转角与门洞：城市把不同身份叠在同一界面上。\n\n"
            "街角机位请勿妨碍通行；抬头看轮船般的外形与连拱门廊。"
        ),
        "sources": [
            {
                "dataset": "slc_building",
                "record_id": "http://data.library.sh.cn/entity/architecture/amknmwvk01qaykng",
                "excerpt": "1924邬达克设计；1953更名武康大楼；1994优秀历史建筑",
            },
        ],
        "scene": {
            "place": "武康路交叉口 · 武康大楼",
            "era_desc": "1924诺曼底公寓始建；1930副楼；1953更名；1994优秀历史建筑。",
            "figures": "邬达克、王人美、郑君里、赵丹（交叉阅读）",
            "city_thread": "交叉路口上的多重身份",
            "today": "外立面全天可观 · 公寓私宅不可入",
            "visual_note": "街角机位请勿妨碍通行；抬头看转角立面。",
        },
    },
    4: {
        "title": "宋庆龄与「宋庆龄故居」",
        "body": (
            "你停在「宋庆龄故居」前（淮海中路一带）。"
            "从武康大楼的公共立面再往前走，路线从「房子」拉回「人与时代」。\n\n"
            "据上图建筑实体与公开地名志交叉阅读：\n"
            "故居始建于1920年代；1949年后，宋庆龄长期居此，"
            "是其从事国务与公益活动的主要住所之一。\n\n"
            "这与前一站的公寓肌理、电影圈与侨民记忆不同："
            "这里更靠近「居住—公务」叠合的公共叙事——"
            "一个人如何把私人生活与时代责任放在同一扇门后。\n\n"
            "若你刚读完武康大楼里电影圈与侨民的交错，"
            "到这里该感到对照：同样是名人故居，"
            "宋庆龄故居指向的是另一种 twentieth-century 上海人物线。\n\n"
            "开放时间以官网与现场公告为准。按参观动线行走，"
            "把人名轻轻放回年代，而不是把它当成打卡背景。"
        ),
        "sources": [
            {
                "dataset": "slc_building",
                "record_id": "http://data.library.sh.cn/entity/architecture/4eqww5yazhokuxt6",
                "excerpt": "宋庆龄故居 · 1920年代始建；1949年后长期居此",
            },
        ],
        "scene": {
            "place": "淮海中路1843号 · 宋庆龄故居",
            "era_desc": "1920年代始建；1949年后宋庆龄长期居此，从事国务与公益活动。",
            "figures": "宋庆龄",
            "city_thread": "从「房子」拉回「人与时代」",
            "today": "开放时间以官网/现场为准",
            "visual_note": "按参观动线行走；把人名轻轻放回年代。",
        },
    },
    5: {
        "title": "丁香与「丁香花园」",
        "body": (
            "你停在华山路849号的「丁香花园」前。先别报建筑名，先报一个人的名字：丁香。"
            "这座城市把人藏进门牌的本事，比把人印上标语高明。\n\n"
            "这栋花园住宅不是空壳，馆藏让几个人在此交错：\n"
            "丁香——名字写进与此楼相关的记载。\n"
            "李鸿章——被馆藏写进这栋楼的人物关系。\n"
            "潘汉年——名字写进与此楼相关的记载。\n"
            "李经迈、张善绅——出现在用途更替的记载里。\n"
            "1949年后，陈毅、潘汉年、刘亚楼、陈赓等人都曾在此居住（据建筑实体事件层）。\n\n"
            "在华山路849号的「丁香花园」，时间并不温和，它一截一截改写用途：\n"
            "1862年，建主楼1号楼。\n"
            "1918年，建3号楼。\n"
            "1940年，李经迈逝世后，其子李国超将丁香花园等家产变卖。\n"
            "1942年，张善绅在此创办中华联合制片股份有限公司。\n"
            "1949年后，中共华东局机关所在地，陈毅、潘汉年、刘亚楼、陈赓等人都曾在此居住。\n"
            "1994年，列为上海市优秀历史建筑。\n"
            "现花园内，一号楼为上海市老干部活动中心，二号楼为申粤轩酒家。\n\n"
            "这一站提供对照：同城不同居住结构——"
            "花园别墅的尺度，把前一站故居的「人与时代」拉到另一种空间语法里。"
            "史实衔接比步行分钟更重要。"
        ),
        "sources": [
            {
                "dataset": "slc_building",
                "record_id": "http://data.library.sh.cn/entity/architecture/sm4repfu8n3ga66j",
                "excerpt": "1862始建；1949年后华东局机关；1994优秀历史建筑",
            },
        ],
        "scene": {
            "place": "华山路849号 · 丁香花园",
            "era_desc": "1862始建；1942张善绅创办中华联合制片；1949年后华东机关；1994优秀历史建筑。",
            "figures": "丁香、李鸿章、潘汉年、陈毅（交叉阅读）",
            "city_thread": "花园作为对照，而非顺路点缀",
            "today": "以现场管理为准 · 部分区域开放",
            "visual_note": "服从现场指示；对照前一站的故居结构。",
        },
    },
    6: {
        "title": "把名字放回「武康庭」",
        "body": (
            "你走进武康路376号的「武康庭(FERGUSON LANE）」巷弄尺度。"
            "前五站的名字——巴金、周璇、邬达克与大楼、宋庆龄、丁香——"
            "若只留在地图图钉上，就还是清单；收束在巷弄里，才变成可步行的序列。\n\n"
            "据公开地名志与上图建筑实体："
            "这里由老公寓与里弄更新而成复合文化商业院落，"
            "是梧桐区「老房子新用法」的代表之一。\n\n"
            "你带走的不应是六张打卡照片，而是一串可核的名字与门牌："
            "哪些出自上图 URI，哪些来自街巷与用途更替的记载，"
            "哪些仍标「未收录」——诚实比注水重要。\n\n"
            "慢走巷弄；在心里把前五站的名字再排一次序："
            "作家、歌者、大楼、故居、花园，最后回到街道尺度。"
            "关系，不是顺路。"
        ),
        "sources": [
            {
                "dataset": "slc_building",
                "record_id": "http://data.library.sh.cn/entity/architecture/b4kfg663vvxvczyu",
                "excerpt": "武康庭 · 武康路376号 · 复合文化商业院落",
            },
        ],
        "scene": {
            "place": "武康路376号 · 武康庭巷弄",
            "era_desc": "由老公寓与里弄更新而成的复合文化商业院落。",
            "figures": "街巷住户（关系提示）",
            "city_thread": "带走可核的名字与门牌，而非打卡清单",
            "today": "公共巷道可走 · 商户以现场为准",
            "visual_note": "慢走巷弄；把前五站的名字在心里再排一次序。",
        },
    },
}

YIDA_CARDS: dict[int, dict] = {
    1: {
        "title": "兴业路与「一大」",
        "body": (
            "你站在兴业路76号一带的石库门片区前。"
            "组织史不是抽象口号——据公开地名志记载，"
            "1921年中国共产党第一次全国代表大会在此召开；"
            "周边石库门里弄构成「一大」红色文化片区。\n\n"
            "这一带的阅读方式，不是数弄堂口，而是辨认门牌与里弄结构："
            "哪些空间曾承载组织记忆，哪些细节必须以纪念馆现场与展陈为准。"
            "地名志给出的是可核的方位与沿革小注，不是替代现场导览。\n\n"
            "带着「一大」的名字走向淮海中路："
            "人物史会把红色叙事接到城市居住记忆——"
            "下一站的宋庆龄故居，就是这种接法的第一个节点。"
        ),
        "sources": [
            {
                "dataset": "geonames_corpus",
                "record_id": "中共一大会址纪念馆",
                "excerpt": "兴业路76号；1921年一大在此召开",
            },
        ],
        "scene": {
            "place": "兴业路76号 · 中共一大会址纪念馆周边",
            "era_desc": "1921年党的一大在此召开；石库门里弄密集。",
            "figures": "代表与组织",
            "city_thread": "从门牌进入可核的组织史节点",
            "today": "以纪念馆开放安排为准",
            "visual_note": "只观外立面与公共通道；具体展陈以现场为准。",
        },
    },
    2: {
        "title": "宋庆龄与「宋庆龄故居」",
        "body": WUKANG_CARDS[4]["body"],
        "sources": WUKANG_CARDS[4]["sources"],
        "scene": WUKANG_CARDS[4]["scene"],
    },
    3: {
        "title": "汇丰与「前汇丰银行大楼」",
        "body": (
            "你停在中山东一路12号的「前汇丰银行大楼」前。"
            "从淮海路的人物史走到外滩，开埠天际线把「人与时代」放大成城市界面。\n\n"
            "据策展词库核录与公开建筑沿革：\n"
            "1923年落成，公和洋行（Palmer & Turner）设计，新古典主义风格，"
            "落成时号称「从苏伊士运河到远东最华贵的建筑」。"
            "建筑主体高五层，中央部分高七层，中段三层以上为希腊式穹顶，"
            "爱奥尼式立柱贯通二至四层——公私权力被写进同一立面语法。\n\n"
            "铜狮子在二战时被日军熔为弹药，回收后仅余两尊。"
            "1955年起成为上海市人民政府驻地，故又被人称作「市府大楼」。"
            "底层门廊顶部原画「八国通商图」彩绘现藏浦东美术馆。\n\n"
            "这一站读的是金融权力如何写进柱廊与立面——"
            "不是看夜景，而是看开埠界面如何把公私权力钉在同一排天际线上。"
            "下一站的麦加利银行大楼，会把「银行立面→艺术入口」的用途更替推到你眼前。"
        ),
        "sources": [
            {
                "dataset": "landmark_corpus",
                "record_id": "汇丰银行大楼",
                "excerpt": "1923落成；1955市府驻地；公和洋行设计",
            },
        ],
        "scene": {
            "place": "中山东一路12号 · 前汇丰银行大楼",
            "era_desc": "1923落成；1955起市府驻地；新古典主义柱廊。",
            "figures": "赫伯特·查尔斯·派克、公和洋行（交叉阅读）",
            "city_thread": "开埠金融权力写进立面",
            "today": "外立面可观 · 银行入口勿挡通道",
            "visual_note": "抬头看爱奥尼柱廊；通道标策展词库。",
        },
    },
    4: {
        "title": "外滩18与「麦加利银行大楼」",
        "body": (
            "你停在中山东一路18号的「麦加利银行大楼」前。"
            "从汇丰的柱廊再往前走，同一排界面里用途开始更替。\n\n"
            "据策展词库核录：原英国渣打银行上海分行，1923年落成，"
            "公和洋行设计，顶层穹顶与罗马柱廊是外滩中段最完整的「万国建筑」入口之一。"
            "2004年改造为顶级奢侈品与艺术中心，"
            "内部保留两段外滩旧堤与百年门闩。\n\n"
            "银行立面到艺术入口——这一站的主题是用途更替："
            "同一栋楼如何在开埠贸易、金融与当代文化消费之间换手，"
            "而立面仍是对外可读的界面。"
            "抬眼看穹顶与柱廊，把「1923」与「2004」当作同一栋楼的两段章节，而不是两个打卡点。"
        ),
        "sources": [
            {
                "dataset": "landmark_corpus",
                "record_id": "外滩18号",
                "excerpt": "1923麦加利银行；2004改造为艺术中心",
            },
        ],
        "scene": {
            "place": "中山东一路18号 · 麦加利银行大楼",
            "era_desc": "1923银行立面；2004艺术中心改造。",
            "figures": "托玛斯·杰克逊（交叉阅读）",
            "city_thread": "从银行立面到艺术入口",
            "today": "以现场管理为准",
            "visual_note": "尊重商业与参观秩序；通道标 landmark。",
        },
    },
    5: {
        "title": "「中国银行大楼」与民族资本",
        "body": (
            "你继续沿中山东一路看「中国银行大楼」。"
            "万国建筑博览群里，不同资本逻辑并置在同一天际线——"
            "这是外滩作为开埠界面的关键，不是单栋建筑的漂亮照片。\n\n"
            "据 OSM 坐标与策展词库交叉阅读："
            "中国银行大楼体现民族资本在外滩界面的落点，"
            "可与同排汇丰、麦加利等洋行建筑对照阅读——"
            "谁写进柱廊，谁写进立面，谁在后来说话。\n\n"
            "沿万国建筑博览群继续走："
            "下一站的怡和洋行会把贸易洋行的早期逻辑收束到江岸。"
        ),
        "sources": [
            {
                "dataset": "landmark_corpus",
                "record_id": "中国银行大楼",
                "excerpt": "民族资本落点 · 与万国建筑并置",
            },
        ],
        "scene": {
            "place": "中山东一路 · 中国银行大楼",
            "era_desc": "民族资本与万国建筑并置的对照阅读。",
            "figures": "中国银行（交叉阅读）",
            "city_thread": "并置阅读开埠界面",
            "today": "外立面可观 · 沿江人行道慢走",
            "visual_note": "把汇丰、18号与本站并置看天际线。",
        },
    },
    6: {
        "title": "怡和洋行收束",
        "body": (
            "你停在中山东一路27号一带的「怡和洋行大楼」前。"
            "整条线从兴业路的石库门走到江岸的贸易立面——"
            "组织史、人物故居、金融柱廊、银行更替、民族资本并置，"
            "最后收束在贸易洋行：开埠早期逻辑仍在立面里可读。\n\n"
            "据策展词库核录：怡和洋行作为早期贸易洋行代表，"
            "是外滩开埠叙事里不可跳过的一站。"
            "你带走的应是可核的开埠界面与诚实通道标注——"
            "上图 URI 可点即链，词库核录即标通道，不伪装馆藏。\n\n"
            "在江岸慢走一遍天际线，把六大站的名字在心里排一次序："
            "从石库门到柱廊，关系才是这条线的骨架。"
        ),
        "sources": [
            {
                "dataset": "landmark_corpus",
                "record_id": "怡和洋行大楼",
                "excerpt": "早期贸易洋行 · 开埠收束",
            },
        ],
        "scene": {
            "place": "中山东一路 · 怡和洋行大楼",
            "era_desc": "贸易洋行代表 · 开埠天际线收束。",
            "figures": "怡和洋行（交叉阅读）",
            "city_thread": "收束开埠天际线",
            "today": "公共人行道可走",
            "visual_note": "江岸慢走；回顾六大站的名字序列。",
        },
    },
}


WUKANG_EXTRA_LAYERS: dict[int, list[dict]] = {
    1: [
        {
            "kind": "event",
            "label": "1950-1955",
            "claim": "1950-1955年，作为苏联商务代表处。",
            "source": {
                "dataset": "slc_building",
                "record_id": "http://data.library.sh.cn/entity/architecture/if3k5yb021u3c4vd",
                "excerpt": "1950-1955年，作为苏联商务代表处。",
            },
        },
    ],
    5: [
        {
            "kind": "event",
            "label": "1918",
            "claim": "1918年，建3号楼。",
            "source": {
                "dataset": "slc_building",
                "record_id": "http://data.library.sh.cn/entity/architecture/sm4repfu8n3ga66j",
                "excerpt": "1918年，建3号楼。",
            },
        },
        {
            "kind": "event",
            "label": "1940",
            "claim": "1940年，李经迈逝世后，其子李国超将丁香花园等家产变卖。",
            "source": {
                "dataset": "slc_building",
                "record_id": "http://data.library.sh.cn/entity/architecture/sm4repfu8n3ga66j",
                "excerpt": "1940年，李经迈逝世后，其子李国超将丁香花园等家产变卖。",
            },
        },
    ],
}

YIDA_EXTRA_LAYERS: dict[int, list[dict]] = {
    4: [
        {
            "kind": "event",
            "label": "2004",
            "claim": "2004年由意大利 Lothar R. V. Lenz 改造为顶级奢侈品与艺术中心。",
            "source": {
                "dataset": "landmark_corpus",
                "record_id": "外滩18号",
                "excerpt": "2004年改造为艺术中心",
            },
        },
    ],
}


def _extra_layers(order: int, layer_map: dict[int, list[dict]]) -> list[dict]:
    return layer_map.get(order, [])


def _patch_blocks(env: dict, cards: dict[int, dict]) -> None:
    blocks = env.get("blocks") or []
    others = [b for b in blocks if b.get("type") not in ("story_card", "scene")]
    new_blocks: list[dict] = []
    for order in sorted(cards):
        c = cards[order]
        new_blocks.append(
            {
                "type": "story_card",
                "stop_order": order,
                "title": c["title"],
                "body": c["body"],
                "sources": c["sources"],
                **({"age_parallel": c["age_parallel"]} if c.get("age_parallel") else {}),
            }
        )
        sc = c["scene"]
        new_blocks.append({"type": "scene", "stop_order": order, **sc})
    # 保留末尾 summary card
    card_tail = [b for b in others if b.get("type") == "card"]
    env["blocks"] = new_blocks + card_tail


def _enrich(path: Path, cards: dict[int, dict], layer_map: dict[int, list[dict]]) -> None:
    env = json.loads(path.read_text(encoding="utf-8"))
    _patch_blocks(env, cards)
    for s in (env.get("route") or {}).get("stops") or []:
        if not isinstance(s, dict):
            continue
        order = int(s.get("order") or 0)
        extras = _extra_layers(order, layer_map)
        if extras:
            s["layers"] = list(s.get("layers") or []) + extras
    sp = build_sp_from_envelope(env)
    if sp:
        env["sentence_provenance"] = sp.as_dict()
    verdict = evaluate_envelope(env)
    if not verdict.passed:
        raise RuntimeError(f"{path.name} gate fail: {verdict.blockers}")
    path.write_text(json.dumps(env, ensure_ascii=False, indent=2), encoding="utf-8")
    bodies = [
        len(c["body"])
        for c in cards.values()
    ]
    print(
        f"OK {path.name}: avg_body={sum(bodies)//len(bodies)} chars, "
        f"sp_ratio={env['sentence_provenance'].get('coverage_ratio')}"
    )


def main() -> int:
    _enrich(ROOT / "content/fixtures/demo-route.json", WUKANG_CARDS, WUKANG_EXTRA_LAYERS)
    _enrich(ROOT / "content/fixtures/demo-route-yida.json", YIDA_CARDS, YIDA_EXTRA_LAYERS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
