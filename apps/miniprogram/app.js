const { API_BASE } = require("./utils/config");

App({
  globalData: {
    apiBase: API_BASE,
    /** @type {import('./utils/types').CurateSession | null} */
    session: null,
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
