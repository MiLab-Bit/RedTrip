const { API_BASE } = require("./utils/config");

App({
  globalData: {
    apiBase: API_BASE,
    /** @type {import('./utils/types').CurateSession | null} */
    session: null,
  },

  onLaunch() {
    this.ensurePrivacyAuthorize();
  },

  ensurePrivacyAuthorize() {
    if (typeof wx.getPrivacySetting !== "function") return;
    wx.getPrivacySetting({
      success: (res) => {
        if (!res.needAuthorization) return;
        // 基础库会弹出系统隐私弹窗；用户同意后再继续网络请求
      },
    });
  },

  /** @param {import('./utils/types').CurateSession} session */
  setSession(session) {
    this.globalData.session = session;
    try {
      wx.setStorageSync("redtrip_session", session);
    } catch (e) {
      console.warn("session storage failed", e);
    }
  },

  getSession() {
    if (this.globalData.session) return this.globalData.session;
    try {
      const cached = wx.getStorageSync("redtrip_session");
      if (cached && cached.envelope) {
        this.globalData.session = cached;
        return cached;
      }
    } catch (e) {
      /* ignore */
    }
    return null;
  },

  clearSession() {
    this.globalData.session = null;
    try {
      wx.removeStorageSync("redtrip_session");
    } catch (e) {
      /* ignore */
    }
  },
});
