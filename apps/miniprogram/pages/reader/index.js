const {
  getStopByOrder,
  getStoryBlock,
  findStopClaims,
  channelLabel,
  datasetLabel,
  shortRecordId,
  splitParagraphs,
  roleLabel,
} = require("../../utils/story");

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
    storyTitle: "",
    paragraphs: [],
    provenanceOpen: false,
    evidenceOpen: false,
    roleLabel: "",
    channelLabel: "",
    storySources: [],
    claimCount: 0,
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
    const claims = findStopClaims(session.envelope, chapter.stopId);
    const stopView = stop
      ? {
          ...stop,
          channelLabel: channelLabel(stop.evidence_channel),
          layers: (stop.layers || []).map((l) => ({
            ...l,
            kindLabel: KIND_LABEL[l.kind] || l.kind,
            datasetLabel: datasetLabel((l.source && l.source.dataset) || ""),
            recordShort: shortRecordId((l.source && l.source.record_id) || ""),
          })),
        }
      : null;

    const paragraphs = splitParagraphs(story && story.body ? story.body : "").map(
      (text, pi) => {
        const matched = claims.filter((c) => {
          const t = (c.text || "").trim();
          return t && (text.includes(t) || t.includes(text));
        });
        const markers = [];
        matched.forEach((c) => {
          (c.fact_uris || []).forEach((u, i) => {
            markers.push({
              uri: u,
              label: (c.fact_labels && c.fact_labels[i]) || "馆藏事实",
              short: shortRecordId(u),
            });
          });
        });
        return { text, markers };
      },
    );

    wx.setNavigationBarTitle({ title: `${chapter.index}. ${chapter.title}` });

    this.setData({
      chapterIndex: index,
      chapter,
      stop: stopView,
      storyTitle: (story && story.title) || chapter.title,
      paragraphs,
      provenanceOpen: false,
      evidenceOpen: false,
      roleLabel: roleLabel(chapter.narrativeRole),
      channelLabel: stopView ? stopView.channelLabel : "",
      storySources: (story && story.sources) || [],
      claimCount: claims.length,
    });
  },

  onToggleProvenance() {
    this.setData({ provenanceOpen: !this.data.provenanceOpen });
  },

  onToggleEvidence() {
    this.setData({ evidenceOpen: !this.data.evidenceOpen });
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
