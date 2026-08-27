const { API_BASE } = require("./config");

function request(path, options = {}) {
  const url = `${API_BASE}${path}`;
  return new Promise((resolve, reject) => {
    wx.request({
      url,
      method: options.method || "GET",
      data: options.data,
      header: {
        "content-type": "application/json",
        ...(options.header || {}),
      },
      timeout: options.timeout || 60000,
      success(res) {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.data);
        } else {
          reject(new Error(`HTTP ${res.statusCode}`));
        }
      },
      fail(err) {
        reject(new Error(err.errMsg || "网络请求失败"));
      },
    });
  });
}

function toOutcome(raw) {
  if (!raw || !raw.envelope) {
    const reasons = (raw && raw.reasons && raw.reasons.filter(Boolean).join("；")) || "未知原因";
    throw new Error("策展未放行：" + reasons);
  }
  const degraded = raw.status !== "ok";
  const notices = degraded
    ? [...(raw.reasons || []), ...((raw.meta && raw.meta.gate && raw.meta.gate.warnings) || [])].filter(Boolean)
    : [];
  return {
    envelope: raw.envelope,
    assumptions: (raw.meta && raw.meta.assumptions) || [],
    hongyuan: (raw.meta && raw.meta.hongyuan) || null,
    degraded,
    notices,
  };
}

function fetchCities() {
  return request("/v1/cities")
    .then((json) => {
      if (Array.isArray(json.cities) && json.cities.length) {
        const list = json.cities.map((c) =>
          c.key === "shanghai" ? { ...c, ready: true, featured: true } : c,
        );
        if (!list.some((c) => c.key === "shanghai")) {
          list.unshift({ key: "shanghai", name_zh: "上海", ready: true, featured: true });
        }
        return list;
      }
      throw new Error("empty");
    })
    .catch(() => require("./defaults").STATIC_CITIES);
}

function suggestPlaces(q, limit = 8) {
  const params = `q=${encodeURIComponent(q || "")}&limit=${limit}`;
  return request(`/v1/places/suggest?${params}`);
}

function curateStart(slots) {
  return request("/v1/curate/start", {
    method: "POST",
    data: { message: null, slots, retry_count: 0 },
  });
}

function curateStatus(taskId) {
  return request(`/v1/curate/status/${taskId}`);
}

function fetchDemoWukang() {
  return request("/v1/demo/wukang").then(toOutcome);
}

function fetchDemoYida() {
  return request("/v1/demo/yida").then(toOutcome);
}

function shortSource(source) {
  if (source === "whitelist") return "馆藏";
  if (source === "corridor") return "走廊";
  if (source === "hotwords") return "热词";
  return source;
}

function metaFromSources(sources, mode) {
  const parts = (sources || []).map(shortSource).filter(Boolean);
  const joined = parts.length ? parts.join(" · ") : "多源";
  return mode === "search" ? `随字 · ${joined}` : `荐读 · ${joined}`;
}

module.exports = {
  API_BASE,
  request,
  toOutcome,
  fetchCities,
  suggestPlaces,
  curateStart,
  curateStatus,
  fetchDemoWukang,
  fetchDemoYida,
  shortSource,
  metaFromSources,
};
