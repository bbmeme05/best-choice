const request = require('../../utils/request');

Page({
  data: {
    query: '',
    loading: false,
    history: [],
    quickTags: ['成都吃饭', '买防晒霜', '看电影', '买耳机', '成都咖啡'],
  },
  onShow() {
    this.loadHistory();
  },
  onQueryInput(e) {
    this.setData({ query: e.detail.value });
  },
  onTagTap(e) {
    this.setData({ query: e.currentTarget.dataset.tag });
    this.onSearch();
  },
  onSearch() {
    const { query } = this.data;
    if (!query.trim()) return;
    this.setData({ loading: true });
    request.post('/api/query', { query }).then(res => {
      this.setData({ loading: false });
      wx.navigateTo({
        url: `/pages/result/result?data=${encodeURIComponent(JSON.stringify(res))}&query=${encodeURIComponent(query)}`
      });
    }).catch(() => {
      this.setData({ loading: false });
      wx.showToast({ title: '请求失败，请重试', icon: 'none' });
    });
  },
  onHistoryTap(e) {
    const { item } = e.currentTarget.dataset;
    const res = { cache_id: item.query_cache_id, result: item.query_cache.result, cache_hit: true };
    wx.navigateTo({
      url: `/pages/result/result?data=${encodeURIComponent(JSON.stringify(res))}&query=${encodeURIComponent(item.query_text)}`
    });
  },
  loadHistory() {
    request.get('/api/user/history').then(data => {
      this.setData({ history: data.slice(0, 5) });
    }).catch(() => {});
  },
});
