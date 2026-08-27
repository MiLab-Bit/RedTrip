function readingLine(h) {
  if (!h) return "";
  if (h.summary) return h.summary;
  const parts = [
    h.emotion && h.emotion.label,
    h.voice_style && h.voice_style.label,
    h.narrative && h.narrative.label,
    h.knowledge_angle && h.knowledge_angle.label,
    h.pacing && h.pacing.label,
  ].filter(Boolean);
  return parts.length ? `${h.agent || "红鸢"}今日读法：${parts.join(" · ")}` : "";
}

Page({
  data: {
    ready: false,
    storyView: null,
    chapters: [],
    cast: [],
    hongyuanLine: "",
    degraded: false,
    notices: [],
  },

  onShow() {
    const session = getApp().getSession();
    if (!session || !session.envelope) {
      wx.redirectTo({ url: "/pages/brief/index" });
      return;
    }
    const { storyView, hongyuan, degraded, notices } = session;
    this.setData({
      ready: true,
      storyView,
      chapters: storyView.chapters || [],
      cast: storyView.cast || [],
      hongyuanLine: readingLine(hongyuan),
      degraded: !!degraded,
      notices: notices || [],
    });
  },

  onBegin() {
    wx.navigateTo({ url: "/pages/reader/index?chapter=0" });
  },

  onRestart() {
    getApp().clearSession();
    wx.reLaunch({ url: "/pages/brief/index" });
  },
});
