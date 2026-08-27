Page({
  data: {
    message: "请稍后再试",
  },

  onLoad(query) {
    if (query.msg) {
      this.setData({ message: decodeURIComponent(query.msg) });
    }
  },

  onRetry() {
    wx.reLaunch({ url: "/pages/brief/index" });
  },

  onDemo() {
    wx.reLaunch({ url: "/pages/brief/index" });
  },
});
