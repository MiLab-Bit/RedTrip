const {
  DEFAULTS,
  STREET_DURATIONS,
  CITY_DURATIONS,
  DAYPARTS,
  TONES,
  COMPANIONS,
  AUDIENCES,
  durationLabel,
} = require("../../utils/defaults");
const {
  fetchCities,
  suggestPlaces,
  fetchDemoWukang,
  fetchDemoYida,
  shortSource,
  metaFromSources,
} = require("../../utils/api");
const { buildStoryView } = require("../../utils/story");

Page({
  data: {
    scene: DEFAULTS.scene,
    durationMin: DEFAULTS.duration_min,
    tone: DEFAULTS.tone,
    companion: DEFAULTS.companions,
    daypart: DEFAULTS.daypart,
    audience: DEFAULTS.audience,
    cityKey: DEFAULTS.city,
    cities: [],
    cityLabels: ["上海（竞赛优先）"],
    cityIndex: 0,
    durations: [],
    tones: TONES,
    companions: COMPANIONS,
    dayparts: DAYPARTS,
    audiences: AUDIENCES,
    suggestions: [],
    suggestOpen: false,
    suggestMeta: "荐读 · 馆藏 · 走廊",
    submitting: false,
  },

  blurTimer: null,
  reqSeq: 0,

  onLoad() {
    const durations = [...STREET_DURATIONS, ...CITY_DURATIONS].map((d) => ({
      value: d,
      label: durationLabel(d),
    }));
    this.setData({ durations });
    this.loadCities();
    this.warmSuggest();
  },

  onUnload() {
    if (this.blurTimer) clearTimeout(this.blurTimer);
  },

  buildSlots() {
    return {
      audience: this.data.audience,
      scene: this.data.scene,
      duration_min: this.data.durationMin,
      tone: this.data.tone,
      delivery: DEFAULTS.delivery,
      companions: this.data.companion,
      daypart: this.data.daypart,
      city: this.data.cityKey,
    };
  },

  async loadCities() {
    try {
      const cities = await fetchCities();
      const labels = cities.map((c) => {
        const suffix = c.featured ? "（竞赛优先）" : !c.ready ? "（数据准备中）" : "";
        return `${c.name_zh}${suffix}`;
      });
      const idx = Math.max(0, cities.findIndex((c) => c.key === this.data.cityKey));
      this.setData({
        cities,
        cityLabels: labels,
        cityIndex: idx >= 0 ? idx : 0,
        cityKey: cities[idx >= 0 ? idx : 0].key,
      });
    } catch (e) {
      console.warn("cities", e);
    }
  },

  async warmSuggest() {
    try {
      const data = await suggestPlaces("", 8);
      const items = this.mapSuggestions(data.items);
      this.setData({
        suggestions: items,
        suggestMeta: metaFromSources(data.sources, data.mode),
      });
      const top = data.items && data.items[0];
      if (top && (!this.data.scene || this.data.scene === DEFAULTS.scene)) {
        this.setData({ scene: top.scene });
      }
    } catch (e) {
      /* input still works */
    }
  },

  mapSuggestions(items) {
    return (items || []).map((item) => ({
      ...item,
      sourceLabel: shortSource(item.source),
    }));
  },

  onCityChange(e) {
    const idx = Number(e.detail.value);
    const city = this.data.cities[idx];
    if (!city) return;
    if (city.key !== "shanghai" && !city.ready) {
      wx.showToast({ title: "该城市数据准备中", icon: "none" });
      return;
    }
    this.setData({ cityIndex: idx, cityKey: city.key });
  },

  onSceneInput(e) {
    const scene = e.detail.value;
    this.setData({ scene, suggestOpen: true });
    this.debouncedSuggest(scene);
  },

  onSceneFocus() {
    if (this.blurTimer) clearTimeout(this.blurTimer);
    this.setData({ suggestOpen: true });
  },

  onSceneBlur() {
    this.blurTimer = setTimeout(() => {
      this.setData({ suggestOpen: false });
    }, 200);
  },

  debouncedSuggest(scene) {
    const seq = ++this.reqSeq;
    clearTimeout(this.suggestTimer);
    this.suggestTimer = setTimeout(async () => {
      try {
        const q = (scene || "").trim();
        const data = await suggestPlaces(q.length >= 1 ? q : "", 8);
        if (seq !== this.reqSeq) return;
        this.setData({
          suggestions: this.mapSuggestions(data.items),
          suggestMeta: metaFromSources(data.sources, data.mode),
        });
      } catch (e) {
        /* keep previous */
      }
    }, 180);
  },

  onPickSuggest(e) {
    const scene = e.currentTarget.dataset.scene;
    this.setData({ scene, suggestOpen: false });
  },

  onDurationTap(e) {
    const val = Number(e.currentTarget.dataset.value);
    this.setData({ durationMin: val });
  },

  onToneTap(e) {
    this.setData({ tone: e.currentTarget.dataset.value });
  },

  onCompanionTap(e) {
    this.setData({ companion: e.currentTarget.dataset.value });
  },

  onDaypartTap(e) {
    this.setData({ daypart: e.currentTarget.dataset.value });
  },

  onAudienceTap(e) {
    this.setData({ audience: e.currentTarget.dataset.value });
  },

  onSubmit() {
    if (this.data.submitting) return;
    const slots = this.buildSlots();
    if (!slots.scene || !slots.scene.trim()) {
      wx.showToast({ title: "请填写起点", icon: "none" });
      return;
    }
    wx.navigateTo({
      url: "/pages/loading/index",
      success(res) {
        res.eventChannel.emit("curate", { slots });
      },
    });
  },

  async openDemo(fetcher, label) {
    if (this.data.submitting) return;
    this.setData({ submitting: true });
    wx.showLoading({ title: `加载${label}…`, mask: true });
    try {
      const outcome = await fetcher();
      this.saveAndGoIntro(outcome);
    } catch (e) {
      wx.showToast({ title: e.message || "演示加载失败", icon: "none", duration: 3000 });
    } finally {
      wx.hideLoading();
      this.setData({ submitting: false });
    }
  },

  onDemoWukang() {
    this.openDemo(fetchDemoWukang, "武康演示");
  },

  onDemoYida() {
    this.openDemo(fetchDemoYida, "外滩演示");
  },

  saveAndGoIntro(outcome) {
    const storyView = buildStoryView(outcome.envelope);
    getApp().setSession({ ...outcome, storyView });
    wx.navigateTo({ url: "/pages/intro/index" });
  },
});
