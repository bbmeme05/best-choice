App({
  globalData: {
    token: null,
    userInfo: null,
    apiBase: 'https://best-choice-production.up.railway.app'
  },
  onLaunch() {
    const token = wx.getStorageSync('token');
    if (token) {
      this.globalData.token = token;
    } else {
      this.login();
    }
  },
  login() {
    wx.login({
      success: (res) => {
        wx.request({
          url: `${this.globalData.apiBase}/api/auth/wx-login`,
          method: 'POST',
          data: { code: res.code },
          success: (resp) => {
            this.globalData.token = resp.data.token;
            this.globalData.userInfo = resp.data.user;
            wx.setStorageSync('token', resp.data.token);
          }
        });
      }
    });
  }
});
