const { curateStart, curateStatus, toOutcome } = require("../../utils/api");
const { buildStoryView } = require("../../utils/story");

const MILESTONES = [
  { at: 22, id: "l1", seal: "证", label: "L1" },
  { at: 48, id: "l2", seal: "签", label: "L2" },
  { at: 72, id: "l3", seal: "今", label: "L3" },
  { at: 96, id: "done", seal: "鸢", label: "成" },
];

const TIPS = [
  "红鸢正在上海图书馆开放数据里翻找证据…",
  "每一句史实都要对得上馆藏编号。",
  "料薄的地方会收着说，不硬编。",
  "路线零件会按你的调性装订成章节。",
];

function layerLabel(stage) {
  const p = stage || "";
  if (/取证|检索|馆藏|证据|whitelist|L1/i.test(p)) return "L1 · 取证";
  if (/抽签|声线|情绪|叙事|润色|装订|红鸢|L2|voice/i.test(p)) return "L2 · 抽签";
  if (/热词|当代|口吻|社交|L3|hotword/i.test(p)) return "L3 · 当代口吻";
  return "红鸢装订中";
}

Page({
  data: {
    progress: 0,
    phaseText: "提交策展任务…",
    layerLabel: "红鸢装订中",
    tip: TIPS[0],
    milestones: MILESTONES.map((m) => ({ ...m, hit: false })),
  },

  taskId: "",
  pollTimer: null,
  tipTimer: null,
  tipIdx: 0,
  cancelled: false,
  slots: null,

  onLoad() {
    const channel = this.getOpenerEventChannel();
    channel.on("curate", ({ slots }) => {
      this.slots = slots;
      this.startCurate();
    });
    this.tipTimer = setInterval(() => {
      this.tipIdx = (this.tipIdx + 1) % TIPS.length;
      this.setData({ tip: TIPS[this.tipIdx] });
    }, 3200);
  },

  onUnload() {
    this.cancelled = true;
    if (this.pollTimer) clearTimeout(this.pollTimer);
    if (this.tipTimer) clearInterval(this.tipTimer);
  },

  async startCurate() {
    try {
      const start = await curateStart(this.slots);
      if (!start.task_id) throw new Error("未返回 task_id");
      this.taskId = start.task_id;
      this.poll();
    } catch (e) {
      this.fail(e.message || "提交失败");
    }
  },

  poll() {
    if (this.cancelled) return;
    curateStatus(this.taskId)
      .then((snap) => {
        if (this.cancelled) return;
        const pct = Math.max(0, Math.min(100, Math.round(snap.progress || 0)));
        const milestones = MILESTONES.map((m) => ({
          ...m,
          hit: pct >= m.at,
        }));
        this.setData({
          progress: pct,
          phaseText: snap.message || snap.stage || "装订中…",
          layerLabel: layerLabel(snap.stage),
          milestones,
        });

        if (snap.status === "done") {
          try {
            const outcome = toOutcome(snap.result);
            const storyView = buildStoryView(outcome.envelope);
            getApp().setSession({ ...outcome, storyView });
            wx.redirectTo({ url: "/pages/intro/index" });
          } catch (e) {
            this.fail(e.message || "结果解析失败");
          }
          return;
        }

        if (snap.status === "error" || snap.error) {
          this.fail(snap.error || snap.message || "策展失败");
          return;
        }

        this.pollTimer = setTimeout(() => this.poll(), 800);
      })
      .catch((e) => {
        if (this.cancelled) return;
        this.fail(e.message || "进度查询失败");
      });
  },

  fail(message) {
    wx.redirectTo({
      url: `/pages/fail/index?msg=${encodeURIComponent(message)}`,
    });
  },

  onCancel() {
    this.cancelled = true;
    wx.navigateBack();
  },
});
