const request = require('../../utils/request');

Page({
  data: {
    prefs: { city: '', budget: '中等', cuisine: [] },
    cuisineOptions: ['辣', '清淡', '川菜', '火锅', '面食', '烧烤', '西餐', '日料'],
    saving: false,
  },
  onShow() {
    request.get('/api/user/profile').then(user => {
      const prefs = user.preferences || {};
      this.setData({
        prefs: {
          city: prefs.city || '',
          budget: prefs.budget || '中等',
          cuisine: prefs.cuisine || [],
        }
      });
    }).catch(() => {});
  },
  onCityInput(e) {
    this.setData({ 'prefs.city': e.detail.value });
  },
  onBudgetTap(e) {
    this.setData({ 'prefs.budget': e.currentTarget.dataset.val });
  },
  onCuisineTap(e) {
    const val = e.currentTarget.dataset.val;
    let cuisine = [...this.data.prefs.cuisine];
    const idx = cuisine.indexOf(val);
    if (idx >= 0) cuisine.splice(idx, 1);
    else cuisine.push(val);
    this.setData({ 'prefs.cuisine': cuisine });
  },
  onSave() {
    this.setData({ saving: true });
    request.put('/api/user/preferences', this.data.prefs).then(() => {
      this.setData({ saving: false });
      wx.showToast({ title: '保存成功', icon: 'success' });
    }).catch(() => {
      this.setData({ saving: false });
      wx.showToast({ title: '保存失败', icon: 'none' });
    });
  },
});
