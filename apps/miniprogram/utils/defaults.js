const DEFAULTS = {
  audience: "成人",
  scene: "武康路一带",
  duration_min: 90,
  tone: "轻社交",
  delivery: "路线",
  companions: "2人",
  daypart: "day",
  city: "shanghai",
};

const STATIC_CITIES = [
  { key: "shanghai", name_zh: "上海", ready: true, featured: true },
  { key: "beijing", name_zh: "北京", ready: false },
  { key: "suzhou", name_zh: "苏州", ready: false },
  { key: "nanjing", name_zh: "南京", ready: false },
  { key: "hangzhou", name_zh: "杭州", ready: false },
];

const STREET_DURATIONS = [30, 60, 90];
const CITY_DURATIONS = [240, 480, 1440];

const DAYPARTS = [
  { id: "day", label: "白天" },
  { id: "night", label: "夜晚" },
  { id: "full", label: "全天" },
  { id: "suburb", label: "郊区" },
];

const TONES = ["文艺", "轻社交", "硬核"];
const COMPANIONS = ["独自", "2人", "3–4人"];
const AUDIENCES = ["成人", "青年", "亲子"];

function durationLabel(d) {
  return d >= 240 ? `${d / 60}小时` : `${d}分`;
}

module.exports = {
  DEFAULTS,
  STATIC_CITIES,
  STREET_DURATIONS,
  CITY_DURATIONS,
  DAYPARTS,
  TONES,
  COMPANIONS,
  AUDIENCES,
  durationLabel,
};
