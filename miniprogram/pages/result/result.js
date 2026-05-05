const request = require('../../utils/request');

Page({
  data: { result: null, query: '', cacheHit: false, cacheId: '', refreshing: false },
  onLoad(options) {
    const data = JSON.parse(decodeURIComponent(options.data));
    const query = decodeURIComponent(options.query);
    this.setData({
      result: data.result,
      query,
      cacheHit: data.cache_hit,
      cacheId: data.cache_id,
    });
  },
  openLink() {
    const { result } = this.data;
    if (result.link) wx.navigateTo({ url: result.link });
  },
  onRefresh() {
    this.setData({ refreshing: true });
    request.post('/api/query/refresh', {
      query: this.data.query,
      exclude_id: this.data.cacheId,
    }).then(res => {
      this.setData({ result: res.result, cacheHit: false, cacheId: res.cache_id, refreshing: false });
    }).catch(() => {
      this.setData({ refreshing: false });
      wx.showToast({ title: '换一个失败', icon: 'none' });
    });
  },
});
