"""多城市注册表：RedTrip 策展覆盖的城市与各自的数据接入配置。

为什么存在：
之前 RAG / 取证 / OSM 拉取全部硬编码「上海」。本模块把城市抽成单一真相源，
供三处复用：
  - rag.py        按城市加载 <city>-osm.json / <city>-landmarks.json，合并每城市场景别名；
  - build_osm_pois.py  按城市生成 OSM 语料（area_query 取自本表）；
  - apps/api /v1/cities  序列化给前端做城市选择器（含 ready 标记）。

城市范围对齐《数据源接入方案》：partner 数据机构所在城市全部列入，另补几座
OSM 覆盖好、策展价值高的主要城市（北京/成都/西安/重庆）。

area_query 用 Overpass「按名取边界」写法（relation["name:zh"="X市"];map_to_area;），
经 maps.mail.ru 镜像验证可用；上海保留原 relation(913067) 以兼容既有语料。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# content/curated 目录（packages/curator/redtrip_curator → RedTrip/content/curated）
_CURATED = Path(__file__).resolve().parents[3] / "content" / "curated"


@dataclass(frozen=True)
class CitySpec:
    key: str                      # 文件名基（<key>-osm.json / <key>-landmarks.json）
    name_zh: str                 # 中文名（UI 展示）
    area_query: str              # Overpass 区域过滤器
    center: tuple[float, float]  # 中心点（仅作兜底/地图初定位）
    # 场景词 → 核心地标检索词（合并进 rag._SCENE_ALIASES，覆盖名字不含场景词的真地标）
    aliases: dict[str, tuple[str, ...]] = field(default_factory=dict)
    # 关联的数据源机构 id（见 library-client/redtrip_library/providers.PROVIDERS）
    partners: tuple[str, ...] = field(default_factory=tuple)

    def osm_path(self, curated: Path | None = None) -> Path:
        base = curated or _CURATED
        return Path(base) / f"{self.key}-osm.json"

    def landmarks_path(self, curated: None | Path = None) -> Path:
        base = curated or _CURATED
        return Path(base) / f"{self.key}-landmarks.json"

    def osm_ready(self, curated: Path | None = None) -> bool:
        p = self.osm_path(curated)
        if not p.exists():
            return False
        try:
            import json
            d = json.loads(p.read_text(encoding="utf-8"))
            return bool(d.get("pois"))
        except Exception:  # noqa: BLE001
            return False

    def as_dict(self, curated: Path | None = None) -> dict[str, Any]:
        # 上海是竞赛主数据线：即使 OSM 扩展语料暂缺，R-20 白名单与上图取证仍可用。
        ready = self.key == DEFAULT_CITY or self.osm_ready(curated)
        return {
            "key": self.key,
            "name_zh": self.name_zh,
            "center": {"lat": self.center[0], "lng": self.center[1]},
            "partners": list(self.partners),
            "ready": ready,
            "featured": self.key == DEFAULT_CITY,
        }


CITY_REGISTRY: dict[str, CitySpec] = {
    "shanghai": CitySpec(
        key="shanghai",
        name_zh="上海",
        area_query="relation(913067);map_to_area;",
        center=(31.2304, 121.4737),
        aliases={
            "外滩": ("外滩", "苏州河", "中山东一路", "外白渡桥"),
            "临港": ("滴水湖", "天文馆", "海昌", "海洋公园"),
            "陆家嘴": ("上海中心", "金茂", "环球金融", "东方明珠", "国金"),
            "豫园": ("豫园", "城隍庙", "九曲桥"),
            "新天地": ("新天地", "一大会址", "太平桥"),
            "北外滩": ("北外滩", "白玉兰", "滨江"),
            "徐汇滨江": ("西岸", "龙美术馆", "油罐"),
            "武康": ("武康", "巴金", "梧桐"),
            "衡山路": ("衡山路", "东平路", "汾阳路"),
            "思南": ("思南公馆", "思南路"),
            "南京路": ("南京东路", "南京路步行街"),
            "静安": ("静安寺", "愚园路"),
            "虹口": ("多伦路", "鲁迅", "1933"),
            "杨浦": ("杨浦滨江", "大学路", "五角场"),
        },
        partners=(
            "slc", "songqingling", "taofen", "jingan", "minhang", "jiading",
            "jinshan", "fengxian", "chongming", "dongfang",
        ),
    ),
    "beijing": CitySpec(
        key="beijing",
        name_zh="北京",
        area_query='relation["name:zh"="北京市"];map_to_area;',
        center=(39.9042, 116.4074),
        aliases={
            "故宫": ("故宫", "紫禁城", "午门", "太和殿"),
            "什刹海": ("什刹海", "后海", "恭王府", "鼓楼"),
            "南锣鼓巷": ("南锣鼓巷", "锣鼓巷", "帽儿胡同"),
            "颐和园": ("颐和园", "万寿山", "昆明湖"),
            "前门": ("前门", "大栅栏", "天桥"),
            "798": ("798", "艺术区", "酒仙桥"),
            "国子监": ("国子监", "孔庙", "雍和宫"),
        },
        partners=("cbdb", "gqbks", "slc"),
    ),
    "suzhou": CitySpec(
        key="suzhou",
        name_zh="苏州",
        area_query='relation["name:zh"="苏州市"];map_to_area;',
        center=(31.2989, 120.5853),
        aliases={
            "拙政园": ("拙政园", "远香堂", "苏州园林"),
            "留园": ("留园", "寒碧山房"),
            "平江路": ("平江路", "平江", "耦园"),
            "虎丘": ("虎丘", "云岩寺塔"),
            "山塘街": ("山塘街", "山塘"),
            "沧浪亭": ("沧浪亭", "沧浪"),
        },
        partners=("suzhou_lib", "suzhou_culture"),
    ),
    "nanjing": CitySpec(
        key="nanjing",
        name_zh="南京",
        area_query='relation["name:zh"="南京市"];map_to_area;',
        center=(32.0603, 118.7969),
        aliases={
            "中山陵": ("中山陵", "钟山", "明孝陵"),
            "总统府": ("总统府", "煦园"),
            "夫子庙": ("夫子庙", "秦淮河", "江南贡院"),
            "明城墙": ("明城墙", "中华门", "台城"),
            "玄武湖": ("玄武湖", "台城"),
            "颐和路": ("颐和路", "公馆"),
        },
        partners=("nanjing_lib",),
    ),
    "hangzhou": CitySpec(
        key="hangzhou",
        name_zh="杭州",
        area_query='relation["name:zh"="杭州市"];map_to_area;',
        center=(30.2741, 120.1551),
        aliases={
            "西湖": ("西湖", "断桥", "苏堤", "白堤", "雷峰塔"),
            "灵隐": ("灵隐寺", "飞来峰"),
            "河坊街": ("河坊街", "清河坊", "南宋御街"),
            "西溪": ("西溪", "湿地"),
            "拱宸桥": ("拱宸桥", "桥西"),
        },
        partners=("zhejiang_lib", "hangya"),
    ),
    "jiaxing": CitySpec(
        key="jiaxing",
        name_zh="嘉兴",
        area_query='relation["name:zh"="嘉兴市"];map_to_area;',
        center=(30.7524, 120.7500),
        aliases={
            "南湖": ("南湖", "红船", "南湖革命纪念馆"),
            "月河": ("月河", "月河街"),
            "乌镇": ("乌镇", "西栅", "东栅"),
            "西塘": ("西塘", "烟雨长廊"),
        },
        partners=("jiaxing_lib",),
    ),
    "yangzhou": CitySpec(
        key="yangzhou",
        name_zh="扬州",
        area_query='relation["name:zh"="扬州市"];map_to_area;',
        center=(32.3941, 119.4145),
        aliases={
            "瘦西湖": ("瘦西湖", "五亭桥", "二十四桥"),
            "个园": ("个园", "东关街"),
            "何园": ("何园", "寄啸山庄"),
            "大明寺": ("大明寺", "栖灵塔"),
        },
        partners=("yangzhou_lib",),
    ),
    "shenzhen": CitySpec(
        key="shenzhen",
        name_zh="深圳",
        area_query='relation["name:zh"="深圳市"];map_to_area;',
        center=(22.5431, 114.0579),
        aliases={
            "华侨城": ("华侨城", "创意文化园", "何香凝美术馆"),
            "莲花山": ("莲花山", "市民中心"),
            "海上世界": ("海上世界", "女娲"),
            "大芬": ("大芬", "油画村"),
            "南头古城": ("南头古城", "南头"),
        },
        partners=("shenzhen_lib",),
    ),
    "nantong": CitySpec(
        key="nantong",
        name_zh="南通",
        area_query='relation["name:zh"="南通市"];map_to_area;',
        center=(31.9800, 120.8933),
        aliases={
            "濠河": ("濠河", "环城河"),
            "狼山": ("狼山", "广教寺"),
            "水绘园": ("水绘园", "如皋"),
            "唐闸": ("唐闸", "古镇", "老街"),
        },
        partners=("nantong_lib",),
    ),
    "guangzhou": CitySpec(
        key="guangzhou",
        name_zh="广州",
        area_query='relation["name:zh"="广州市"];map_to_area;',
        center=(23.1291, 113.2644),
        aliases={
            "沙面": ("沙面", "租界"),
            "陈家祠": ("陈家祠", "陈氏书院"),
            "北京路": ("北京路", "千年古道"),
            "荔枝湾": ("荔枝湾", "荔湾", "西关"),
            "黄埔": ("黄埔", "军校"),
        },
        partners=("souyun",),
    ),
    "hefei": CitySpec(
        key="hefei",
        name_zh="合肥·安徽",
        area_query='relation["name:zh"="合肥市"];map_to_area;',
        center=(31.8206, 117.2272),
        aliases={
            "包公祠": ("包公祠", "包河", "包公园"),
            "逍遥津": ("逍遥津", "逍遥津公园"),
            "三河": ("三河", "古镇"),
            "李鸿章": ("李鸿章故居", "李鸿章"),
        },
        partners=("anhui_lib",),
    ),
    "chengdu": CitySpec(
        key="chengdu",
        name_zh="成都",
        area_query='relation["name:zh"="成都市"];map_to_area;',
        center=(30.5728, 104.0668),
        aliases={
            "宽窄巷子": ("宽窄巷子", "宽巷子", "窄巷子"),
            "锦里": ("锦里", "武侯祠"),
            "杜甫草堂": ("杜甫草堂", "草堂"),
            "青羊宫": ("青羊宫", "青羊"),
            "望江楼": ("望江楼", "薛涛"),
        },
        partners=(),
    ),
    "xian": CitySpec(
        key="xian",
        name_zh="西安",
        area_query='relation["name:zh"="西安市"];map_to_area;',
        center=(34.3416, 108.9398),
        aliases={
            "城墙": ("城墙", "钟楼", "鼓楼", "永宁门"),
            "大雁塔": ("大雁塔", "慈恩寺", "大唐不夜城"),
            "碑林": ("碑林", "碑林博物馆"),
            "回民街": ("回民街", "北院门"),
            "大明宫": ("大明宫", "遗址"),
        },
        partners=(),
    ),
    "chongqing": CitySpec(
        key="chongqing",
        name_zh="重庆",
        area_query='relation["name:zh"="重庆市"];map_to_area;',
        center=(29.5630, 106.5516),
        aliases={
            "洪崖洞": ("洪崖洞", "吊脚楼"),
            "磁器口": ("磁器口", "古镇"),
            "解放碑": ("解放碑", "朝天门"),
            "湖广会馆": ("湖广会馆", "会馆"),
            "李子坝": ("李子坝", "轻轨"),
        },
        partners=(),
    ),
}

DEFAULT_CITY = "shanghai"


def get_city(key: str | None) -> CitySpec:
    """按 key 取城市；空/未知 → 默认上海（兼容旧调用）。"""
    if not key:
        return CITY_REGISTRY[DEFAULT_CITY]
    return CITY_REGISTRY.get(key, CITY_REGISTRY[DEFAULT_CITY])


def list_cities(curated: Path | None = None) -> list[dict[str, Any]]:
    return [c.as_dict(curated) for c in CITY_REGISTRY.values()]


def merged_scene_aliases() -> dict[str, tuple[str, ...]]:
    """合并所有城市的场景别名，供 rag._SCENE_ALIASES 使用。"""
    out: dict[str, tuple[str, ...]] = {}
    for c in CITY_REGISTRY.values():
        for k, v in c.aliases.items():
            out.setdefault(k, tuple())  # 首座城市优先；不覆盖
            if not out[k]:
                out[k] = v
    return out
