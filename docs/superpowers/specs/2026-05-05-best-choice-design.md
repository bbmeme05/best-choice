# Best Choice — 产品设计文档

**日期：** 2026-05-05  
**项目：** Best Choice  
**状态：** 已确认，待实施

---

## 产品目标

帮助有选择困难症的用户，在任何场景下只给出**一个当前最优解**，而不是一堆列表。用户输入自然语言问题（如"我想在成都吃面"），系统直接返回一个带完整信息的推荐卡片。

---

## 平台策略

- **第一阶段：** 微信小程序（原生 WXML/WXSS）
- **第二阶段：** 验证产品价值后扩展为独立 App（iOS/Android）

---

## 整体架构

```
微信小程序（原生 WXML）
        ↓ HTTPS
Python FastAPI（单体服务，内部模块化）
  ├── query_router       # 判断命中缓存还是走 AI
  ├── ai_module          # Kimi API 联网搜索 + 生成爬虫脚本
  ├── crawler_module     # 执行爬虫脚本、数据入库
  ├── scheduler          # APScheduler 管理定时任务
  └── user_profile       # 用户画像、历史记录
        ↓
Supabase
  ├── PostgreSQL          # 用户表、任务表、推荐结果表
  ├── pgvector            # 向量语义搜索（query embedding）
  ├── Auth                # 微信一键登录
  └── Storage             # 爬虫脚本文件存储

部署：Railway（后端）+ Supabase（托管数据层）
```

---

## 核心数据流

1. 用户输入 → 小程序 → FastAPI
2. FastAPI 生成 query embedding，在 pgvector 里做余弦相似度搜索（阈值 > 0.85 视为命中）
3. **命中缓存** → 取已有推荐结果，结合用户 preferences 做轻量个性化润色 → 返回（毫秒级）
4. **未命中** → 调 Kimi API 联网搜索 → AI 分析生成推荐 + 爬虫脚本 + 生命周期评估 → 存库 → 创建定时任务 → 返回结果

---

## 数据模型

### users 表
| 字段 | 类型 | 说明 |
|------|------|------|
| id | uuid | 主键 |
| wx_openid | text | 微信唯一标识 |
| nickname | text | 昵称 |
| avatar | text | 头像 URL |
| preferences | jsonb | `{"cuisine":["辣"],"budget":"中等","city":"成都"}` |
| location | text | 常驻城市 |
| created_at | timestamp | |

### query_cache 表
| 字段 | 类型 | 说明 |
|------|------|------|
| id | uuid | 主键 |
| query_embedding | vector(1536) | 用于语义匹配 |
| canonical_query | text | 标准化问题，如"成都 吃面 推荐" |
| result | jsonb | 推荐结果：名称、理由、地址、价格、链接 |
| hit_count | int | 命中次数 |
| last_hit_at | timestamp | 最近命中时间 |
| expires_at | timestamp | AI 评估的过期时间 |
| created_at | timestamp | |

### crawler_tasks 表
| 字段 | 类型 | 说明 |
|------|------|------|
| id | uuid | 主键 |
| query_cache_id | uuid | 关联缓存 |
| script_path | text | Supabase Storage 中的爬虫脚本路径 |
| status | text | `pending / running / done / expired` |
| schedule_interval | text | AI 定的更新频率，如 `7d` / `30d` |
| lifecycle_type | text | `evergreen`（长期）/ `seasonal`（季节性）/ `ephemeral`（短期） |
| next_run_at | timestamp | 下次执行时间 |
| expires_at | timestamp | 超过此时间无命中则删除任务 |

### user_query_history 表
| 字段 | 类型 | 说明 |
|------|------|------|
| id | uuid | 主键 |
| user_id | uuid | 关联用户 |
| query_text | text | 原始输入 |
| query_cache_id | uuid | 命中的缓存 |
| created_at | timestamp | |

---

## 核心业务流程

### 查询流程
```
用户输入
  → 生成 query embedding
  → pgvector 余弦相似度搜索（阈值 > 0.85 视为命中）
  → 命中：取 result，结合用户 preferences 做轻量个性化润色 → 返回
  → 未命中：
      1. 调 Kimi API 联网搜索，获取原始数据
      2. AI 分析 → 生成推荐结果（含名称/理由/地址/价格/链接）
      3. AI 生成针对该数据源的 Python 爬虫脚本
      4. AI 评估 lifecycle_type 和 schedule_interval
      5. 存入 query_cache + crawler_tasks
      6. 返回推荐结果
```

### 定时任务流程（APScheduler，进程内）
```
每次 crawler_task 到 next_run_at：
  → 执行爬虫脚本，抓取最新数据
  → AI 重新分析 → 更新 query_cache.result
  → 更新 next_run_at

冷数据清理（每日跑一次）：
  → 查找 expires_at < now() 且 last_hit_at 超过阈值的任务
  → 删除 crawler_task + 对应 query_cache
```

### 个性化润色（轻量，不重新调 AI）
```
推荐结果返回前：
  → 读取 user.preferences（预算、口味等）
  → 用模板规则在结果描述中插入个性化说明
  → 如用户预算"低"，在价格字段加"符合你的预算"标注
```

---

## 小程序前端结构

**页面**
- **首页：** 搜索框（"我想..."，支持语音）+ 热门快捷入口（美食/购物/出行/娱乐）+ 历史记录
- **推荐结果页：** 推荐卡片（名称 + 理由 + 地址/价格/评分 + 跳转按钮）+ "换一个"按钮
- **个人中心页：** 偏好设置（口味/预算/常驻城市）+ 历史记录

**Auth 流程：** `wx.login()` → code → 后端换取 openid → Supabase Auth 创建用户 → 返回 JWT

---

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/query` | 查询推荐，body: `{query, location?}` |
| POST | `/api/query/refresh` | 换一个，body: `{query, exclude_id}` |
| POST | `/api/auth/wx-login` | 微信登录，body: `{code}` |
| GET | `/api/user/profile` | 获取用户画像 |
| PUT | `/api/user/preferences` | 更新偏好设置 |
| GET | `/api/user/history` | 获取历史记录 |

---

## 部署

```
Railway
  └── FastAPI 服务（单容器，Dockerfile）
      └── 环境变量：KIMI_API_KEY, SUPABASE_URL, SUPABASE_KEY

Supabase（托管）
  └── PostgreSQL + pgvector + Auth + Storage

本地开发：
  └── docker-compose.yml（FastAPI + supabase start 本地模拟）
```

---

## 测试策略

**单元测试（pytest）**
- `query_router`：命中 / 未命中逻辑
- `ai_module`：mock Kimi API，验证输出格式
- `scheduler`：任务创建、过期删除逻辑

**集成测试**
- 全链路：输入 query → 返回推荐结果（Kimi API 使用 mock）

**小程序手工验收**
- 首次查询、缓存命中、"换一个"、偏好设置

---

## MVP 里程碑

| 周次 | 目标 |
|------|------|
| Week 1 | FastAPI 骨架 + Supabase 建表 + Kimi 接入 + 查询路由 |
| Week 2 | 爬虫脚本生成 + APScheduler 定时任务 + 小程序基础界面 |
| Week 3 | 个性化润色 + 用户画像 + 冷数据清理逻辑 |
| Week 4 | 完整联调 + Railway 部署 + 小程序审核提交 |
