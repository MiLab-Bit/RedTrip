const { getStopByOrder, getStoryBlock, roleLabel } = require("../../utils/story");

const KIND_LABEL = {
  building: "建筑",
  event: "事件",
  era: "时代",
  poem: "诗文",
  person: "人物",
  geoname: "地名",
  literary: "文献",
};

Page({
  data: {
    ready: false,
    chapterIndex: 0,
    total: 0,
    chapters: [],
    chapter: null,
    stop: null,
    storyBody: "",
    roleLabel: "",
  },

  session: null,

  onLoad(query) {
    const idx = Number(query.chapter || 0);
    this.initialIndex = Number.isFinite(idx) ? idx : 0;
  },

  onShow() {
    const session = getApp().getSession();
    if (!session || !session.envelope) {
      wx.redirectTo({ url: "/pages/brief/index" });
      return;
    }
    this.session = session;
    const chapters = session.storyView.chapters || [];
    const chapterIndex = Math.max(0, Math.min(chapters.length - 1, this.initialIndex));
    this.setData({
      ready: true,
      total: chapters.length,
      chapters,
      chapterIndex,
    });
    this.renderChapter(chapterIndex);
  },

  renderChapter(index) {
    const session = this.session;
    const chapters = session.storyView.chapters;
    const chapter = chapters[index];
    const stop = getStopByOrder(session.envelope, chapter.stopId);
    const story = getStoryBlock(session.envelope, chapter.stopId);
    const stopView = stop
      ? {
          ...stop,
          layers: (stop.layers || []).map((l) => ({
            ...l,
            kindLabel: KIND_LABEL[l.kind] || l.kind,
          })),
        }
      : null;

    wx.setNavigationBarTitle({ title: `${chapter.index}. ${chapter.title}` });

    this.setData({
      chapterIndex: index,
      chapter,
      stop: stopView,
      storyBody: story && story.body ? story.body : "",
      roleLabel: roleLabel(chapter.narrativeRole),
    });
  },

  onPrev() {
    if (this.data.chapterIndex <= 0) return;
    this.renderChapter(this.data.chapterIndex - 1);
  },

  onNext() {
    if (this.data.chapterIndex >= this.data.total - 1) return;
    this.renderChapter(this.data.chapterIndex + 1);
  },

  onJump(e) {
    const index = Number(e.currentTarget.dataset.index);
    this.renderChapter(index);
  },

  onFinish() {
    wx.showModal({
      title: "这一程读完了",
      content: "要重新出题，还是留在序章回顾脉络？",
      confirmText: "重新出题",
      cancelText: "回序章",
      success(res) {
        if (res.confirm) {
          getApp().clearSession();
          wx.reLaunch({ url: "/pages/brief/index" });
        } else {
          wx.navigateBack();
        }
      },
    });
  },
});
