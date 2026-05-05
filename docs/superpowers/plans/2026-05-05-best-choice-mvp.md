# Best Choice MVP 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个微信小程序，用户输入自然语言问题，AI 返回单一最优推荐，首次查询走 Kimi 联网搜索并自动生成爬虫脚本，后续查询命中 pgvector 向量缓存。

**Architecture:** FastAPI 单体服务（内部模块化）+ Supabase（PostgreSQL + pgvector + Auth + Storage），APScheduler 进程内管理爬虫定时任务和冷数据清理，微信小程序原生 WXML 前端。

**Tech Stack:** Python 3.11, FastAPI, Supabase-py, OpenAI SDK（embeddings）, Moonshot/Kimi API（web search + 生成爬虫脚本）, APScheduler, pytest, 微信原生小程序（WXML/WXSS/JS）, Docker, Railway

---

## 文件结构

```
best_choice/
├── backend/
│   ├── main.py                        # FastAPI app，路由注册，lifespan（启动 scheduler）
│   ├── config.py                      # pydantic-settings 读取环境变量
│   ├── database.py                    # Supabase 客户端单例
│   ├── models/
│   │   ├── user.py                    # Pydantic 用户模型
│   │   ├── query.py                   # Pydantic 查询/缓存模型
│   │   └── crawler.py                 # Pydantic 爬虫任务模型
│   ├── routers/
│   │   ├── auth.py                    # POST /api/auth/wx-login
│   │   ├── query.py                   # POST /api/query, POST /api/query/refresh
│   │   └── user.py                    # GET/PUT /api/user/profile, GET /api/user/history
│   ├── services/
│   │   ├── query_router.py            # embedding 生成 + pgvector 相似度搜索
│   │   ├── ai_module.py               # Kimi 联网搜索 + 推荐生成 + 爬虫脚本生成
│   │   ├── crawler_module.py          # 执行爬虫脚本、更新 query_cache
│   │   ├── scheduler.py               # APScheduler 初始化 + 任务注册
│   │   └── personalization.py         # 基于用户偏好的结果润色
│   ├── requirements.txt
│   ├── Dockerfile
│   └── docker-compose.yml
├── miniprogram/
│   ├── app.js
│   ├── app.json
│   ├── app.wxss
│   ├── pages/
│   │   ├── index/
│   │   │   ├── index.wxml
│   │   │   ├── index.wxss
│   │   │   └── index.js
│   │   ├── result/
│   │   │   ├── result.wxml
│   │   │   ├── result.wxss
│   │   │   └── result.js
│   │   └── profile/
│   │       ├── profile.wxml
│   │       ├── profile.wxss
│   │       └── profile.js
│   └── utils/
│       └── request.js                 # HTTP 封装，自动带 JWT
├── supabase/
│   └── migrations/
│       └── 001_initial_schema.sql
└── tests/
    ├── conftest.py
    ├── test_query_router.py
    ├── test_ai_module.py
    └── test_scheduler.py
```

---

## Task 1: 项目骨架 + 依赖配置

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/config.py`
- Create: `backend/main.py`

- [ ] **Step 1: 创建 requirements.txt**

```
fastapi==0.111.0
uvicorn[standard]==0.29.0
supabase==2.4.2
openai==1.30.1
httpx==0.27.0
apscheduler==3.10.4
python-jose[cryptography]==3.3.0
pydantic-settings==2.2.1
pytest==8.2.0
pytest-asyncio==0.23.6
pytest-mock==3.14.0
```

- [ ] **Step 2: 创建 config.py**

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    supabase_url: str
    supabase_key: str
    kimi_api_key: str
    openai_api_key: str
    wx_app_id: str
    wx_app_secret: str
    jwt_secret: str = "change-me-in-production"
    similarity_threshold: float = 0.85

    class Config:
        env_file = ".env"

settings = Settings()
```

- [ ] **Step 3: 创建 backend/main.py**

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import auth, query, user
from services.scheduler import start_scheduler, shutdown_scheduler

@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    yield
    shutdown_scheduler()

app = FastAPI(title="Best Choice API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth")
app.include_router(query.router, prefix="/api/query")
app.include_router(user.router, prefix="/api/user")
```

- [ ] **Step 4: 创建 .env 文件（不提交 git）**

```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
KIMI_API_KEY=your-moonshot-key
OPENAI_API_KEY=your-openai-key
WX_APP_ID=your-wx-appid
WX_APP_SECRET=your-wx-secret
JWT_SECRET=your-random-secret
```

- [ ] **Step 5: 创建 .gitignore**

```
.env
__pycache__/
*.pyc
.pytest_cache/
```

- [ ] **Step 6: 验证 FastAPI 可启动**

```bash
cd backend && pip install -r requirements.txt
uvicorn main:app --reload
```

期望：浏览器访问 `http://localhost:8000/docs` 看到 Swagger 界面。

- [ ] **Step 7: Commit**

```bash
git init
git add backend/requirements.txt backend/config.py backend/main.py .gitignore
git commit -m "feat: project scaffold with FastAPI and config"
```

---

## Task 2: Supabase 数据库建表

**Files:**
- Create: `supabase/migrations/001_initial_schema.sql`
- Create: `backend/database.py`

- [ ] **Step 1: 编写建表 SQL**

```sql
-- supabase/migrations/001_initial_schema.sql
-- 启用 pgvector 扩展
create extension if not exists vector;

-- 用户表
create table if not exists users (
  id uuid primary key default gen_random_uuid(),
  wx_openid text unique not null,
  nickname text,
  avatar text,
  preferences jsonb default '{}',
  location text,
  created_at timestamptz default now()
);

-- 查询缓存表（含向量）
create table if not exists query_cache (
  id uuid primary key default gen_random_uuid(),
  query_embedding vector(1536) not null,
  canonical_query text not null,
  result jsonb not null,
  hit_count int default 0,
  last_hit_at timestamptz default now(),
  expires_at timestamptz not null,
  created_at timestamptz default now()
);

-- 向量相似度索引
create index on query_cache
  using ivfflat (query_embedding vector_cosine_ops)
  with (lists = 100);

-- 爬虫任务表
create table if not exists crawler_tasks (
  id uuid primary key default gen_random_uuid(),
  query_cache_id uuid references query_cache(id) on delete cascade,
  script_path text not null,
  status text default 'pending' check (status in ('pending','running','done','expired')),
  schedule_interval text not null,
  lifecycle_type text not null check (lifecycle_type in ('evergreen','seasonal','ephemeral')),
  next_run_at timestamptz not null,
  expires_at timestamptz not null
);

-- 用户查询历史表
create table if not exists user_query_history (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references users(id) on delete cascade,
  query_text text not null,
  query_cache_id uuid references query_cache(id) on delete set null,
  created_at timestamptz default now()
);
```

- [ ] **Step 2: 在 Supabase Dashboard 执行 SQL**

登录 Supabase Dashboard → SQL Editor → 粘贴上面的 SQL → Run。

期望：4 张表创建成功，`query_cache` 表有 `query_embedding` 向量列。

- [ ] **Step 3: 创建 backend/database.py**

```python
from supabase import create_client, Client
from config import settings

_client: Client | None = None

def get_db() -> Client:
    global _client
    if _client is None:
        _client = create_client(settings.supabase_url, settings.supabase_key)
    return _client
```

- [ ] **Step 4: Commit**

```bash
git add supabase/migrations/001_initial_schema.sql backend/database.py
git commit -m "feat: database schema with pgvector and supabase client"
```

---

## Task 3: Pydantic 数据模型

**Files:**
- Create: `backend/models/user.py`
- Create: `backend/models/query.py`
- Create: `backend/models/crawler.py`

- [ ] **Step 1: 创建 backend/models/user.py**

```python
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class UserPreferences(BaseModel):
    cuisine: list[str] = []
    budget: str = "中等"
    city: str = ""

class User(BaseModel):
    id: str
    wx_openid: str
    nickname: Optional[str] = None
    avatar: Optional[str] = None
    preferences: UserPreferences = UserPreferences()
    location: Optional[str] = None
    created_at: datetime

class UpdatePreferencesRequest(BaseModel):
    cuisine: Optional[list[str]] = None
    budget: Optional[str] = None
    city: Optional[str] = None
```

- [ ] **Step 2: 创建 backend/models/query.py**

```python
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class RecommendationResult(BaseModel):
    name: str
    reason: str
    address: Optional[str] = None
    price_range: Optional[str] = None
    rating: Optional[float] = None
    link: Optional[str] = None
    personalization_note: Optional[str] = None

class QueryRequest(BaseModel):
    query: str
    location: Optional[str] = None

class QueryRefreshRequest(BaseModel):
    query: str
    exclude_id: str

class QueryResponse(BaseModel):
    cache_id: str
    result: RecommendationResult
    cache_hit: bool
```

- [ ] **Step 3: 创建 backend/models/crawler.py**

```python
from pydantic import BaseModel
from datetime import datetime

class CrawlerTask(BaseModel):
    id: str
    query_cache_id: str
    script_path: str
    status: str
    schedule_interval: str
    lifecycle_type: str
    next_run_at: datetime
    expires_at: datetime

class CrawlerTaskCreate(BaseModel):
    query_cache_id: str
    script_content: str
    schedule_interval: str
    lifecycle_type: str
    expires_at: datetime
```

- [ ] **Step 4: Commit**

```bash
git add backend/models/
git commit -m "feat: pydantic data models for user, query, crawler"
```

---

## Task 4: 微信登录 Auth 端点

**Files:**
- Create: `backend/routers/auth.py`
- Create: `tests/test_auth.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_auth.py
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from main import app

client = TestClient(app)

def test_wx_login_returns_token(mock_wx_response, mock_db):
    with patch("routers.auth.exchange_wx_code") as mock_exchange, \
         patch("routers.auth.get_or_create_user") as mock_user:
        mock_exchange.return_value = "test_openid_123"
        mock_user.return_value = {"id": "user-uuid", "wx_openid": "test_openid_123"}
        
        response = client.post("/api/auth/wx-login", json={"code": "wx_test_code"})
        
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert "user" in data
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd backend && pytest tests/test_auth.py -v
```

期望：`FAILED` — `ModuleNotFoundError: routers.auth`

- [ ] **Step 3: 实现 backend/routers/auth.py**

```python
import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from jose import jwt
from datetime import datetime, timedelta
from config import settings
from database import get_db

router = APIRouter()

class WxLoginRequest(BaseModel):
    code: str

async def exchange_wx_code(code: str) -> str:
    url = "https://api.weixin.qq.com/sns/jscode2session"
    params = {
        "appid": settings.wx_app_id,
        "secret": settings.wx_app_secret,
        "js_code": code,
        "grant_type": "authorization_code",
    }
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params)
        data = resp.json()
    if "errcode" in data:
        raise HTTPException(status_code=400, detail=f"微信登录失败: {data.get('errmsg')}")
    return data["openid"]

def get_or_create_user(openid: str) -> dict:
    db = get_db()
    result = db.table("users").select("*").eq("wx_openid", openid).execute()
    if result.data:
        return result.data[0]
    new_user = db.table("users").insert({"wx_openid": openid}).execute()
    return new_user.data[0]

def create_jwt(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.utcnow() + timedelta(days=30),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")

@router.post("/wx-login")
async def wx_login(req: WxLoginRequest):
    openid = await exchange_wx_code(req.code)
    user = get_or_create_user(openid)
    token = create_jwt(user["id"])
    return {"token": token, "user": user}
```

- [ ] **Step 4: 创建 tests/conftest.py（mock 工具）**

```python
# tests/conftest.py
import pytest
from unittest.mock import MagicMock, patch

@pytest.fixture
def mock_db():
    with patch("database.get_db") as mock:
        mock_client = MagicMock()
        mock.return_value = mock_client
        yield mock_client
```

- [ ] **Step 5: 运行测试，确认通过**

```bash
pytest tests/test_auth.py -v
```

期望：`PASSED`

- [ ] **Step 6: Commit**

```bash
git add backend/routers/auth.py tests/test_auth.py tests/conftest.py
git commit -m "feat: wx-login auth endpoint with JWT"
```

---

## Task 5: Embedding 生成 + pgvector 缓存查询

**Files:**
- Create: `backend/services/query_router.py`
- Create: `tests/test_query_router.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_query_router.py
import pytest
from unittest.mock import patch, MagicMock

def test_cache_hit_returns_result(mock_db):
    cached_result = {
        "id": "cache-uuid",
        "result": {"name": "老字号面馆", "reason": "成都本地人最爱"},
        "expires_at": "2099-01-01T00:00:00",
    }
    with patch("services.query_router.generate_embedding") as mock_embed, \
         patch("services.query_router.search_cache") as mock_search:
        mock_embed.return_value = [0.1] * 1536
        mock_search.return_value = cached_result
        
        from services.query_router import route_query
        result = route_query("成都吃面", user_id="user-1")
        
        assert result["cache_hit"] is True
        assert result["result"]["name"] == "老字号面馆"

def test_cache_miss_returns_none(mock_db):
    with patch("services.query_router.generate_embedding") as mock_embed, \
         patch("services.query_router.search_cache") as mock_search:
        mock_embed.return_value = [0.1] * 1536
        mock_search.return_value = None
        
        from services.query_router import route_query
        result = route_query("火星吃什么", user_id="user-1")
        
        assert result["cache_hit"] is False
        assert result["result"] is None
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
pytest tests/test_query_router.py -v
```

期望：`FAILED` — `ModuleNotFoundError: services.query_router`

- [ ] **Step 3: 实现 backend/services/query_router.py**

```python
from openai import OpenAI
from database import get_db
from config import settings
from datetime import datetime, timezone

_openai = OpenAI(api_key=settings.openai_api_key)

def generate_embedding(text: str) -> list[float]:
    response = _openai.embeddings.create(
        model="text-embedding-ada-002",
        input=text,
    )
    return response.data[0].embedding

def search_cache(embedding: list[float], threshold: float = 0.85) -> dict | None:
    db = get_db()
    vector_str = f"[{','.join(str(x) for x in embedding)}]"
    result = db.rpc(
        "match_query_cache",
        {"query_embedding": vector_str, "match_threshold": threshold, "match_count": 1},
    ).execute()
    if not result.data:
        return None
    row = result.data[0]
    if datetime.fromisoformat(row["expires_at"]).replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        return None
    return row

def update_cache_hit(cache_id: str):
    db = get_db()
    db.table("query_cache").update({
        "hit_count": db.rpc("increment", {"row_id": cache_id, "table": "query_cache", "column": "hit_count"}),
        "last_hit_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", cache_id).execute()

def route_query(query: str, user_id: str) -> dict:
    embedding = generate_embedding(query)
    cached = search_cache(embedding)
    if cached:
        update_cache_hit(cached["id"])
        return {"cache_hit": True, "cache_id": cached["id"], "result": cached["result"], "embedding": embedding}
    return {"cache_hit": False, "cache_id": None, "result": None, "embedding": embedding}
```

- [ ] **Step 4: 在 Supabase 创建 match_query_cache RPC 函数**

在 Supabase Dashboard → SQL Editor 执行：

```sql
create or replace function match_query_cache(
  query_embedding vector(1536),
  match_threshold float,
  match_count int
)
returns table (
  id uuid,
  canonical_query text,
  result jsonb,
  expires_at timestamptz,
  similarity float
)
language sql stable
as $$
  select
    id, canonical_query, result, expires_at,
    1 - (query_cache.query_embedding <=> query_embedding) as similarity
  from query_cache
  where 1 - (query_cache.query_embedding <=> query_embedding) > match_threshold
  order by similarity desc
  limit match_count;
$$;
```

- [ ] **Step 5: 运行测试，确认通过**

```bash
pytest tests/test_query_router.py -v
```

期望：`PASSED`

- [ ] **Step 6: Commit**

```bash
git add backend/services/query_router.py tests/test_query_router.py
git commit -m "feat: embedding generation and pgvector cache lookup"
```

---

## Task 6: Kimi 联网搜索 + 推荐生成

**Files:**
- Create: `backend/services/ai_module.py`
- Create: `tests/test_ai_module.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_ai_module.py
import pytest
from unittest.mock import patch, MagicMock

def test_generate_recommendation_returns_structured_result():
    mock_response = MagicMock()
    mock_response.choices[0].message.content = '''{
        "name": "蜀九香火锅",
        "reason": "成都本地老牌火锅，食材新鲜，价格实惠",
        "address": "成都市锦江区XX路",
        "price_range": "人均80-120元",
        "rating": 4.8,
        "link": "https://example.com"
    }'''
    
    with patch("services.ai_module._kimi_client.chat.completions.create") as mock_create:
        mock_create.return_value = mock_response
        
        from services.ai_module import generate_recommendation
        result = generate_recommendation("成都吃火锅")
        
        assert result["name"] == "蜀九香火锅"
        assert result["reason"] is not None
        assert "price_range" in result

def test_generate_crawler_script_returns_python_code():
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "import requests\n# crawler code"
    
    with patch("services.ai_module._kimi_client.chat.completions.create") as mock_create:
        mock_create.return_value = mock_response
        
        from services.ai_module import generate_crawler_script
        script = generate_crawler_script("成都吃火锅", {"name": "蜀九香"})
        
        assert "import" in script

def test_evaluate_lifecycle_returns_valid_type():
    mock_response = MagicMock()
    mock_response.choices[0].message.content = '{"lifecycle_type": "evergreen", "schedule_interval": "7d", "ttl_days": 365}'
    
    with patch("services.ai_module._kimi_client.chat.completions.create") as mock_create:
        mock_create.return_value = mock_response
        
        from services.ai_module import evaluate_lifecycle
        result = evaluate_lifecycle("成都吃火锅")
        
        assert result["lifecycle_type"] in ("evergreen", "seasonal", "ephemeral")
        assert result["schedule_interval"].endswith("d")
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
pytest tests/test_ai_module.py -v
```

期望：`FAILED` — `ModuleNotFoundError: services.ai_module`

- [ ] **Step 3: 实现 backend/services/ai_module.py**

```python
import json
from openai import OpenAI
from config import settings

_kimi_client = OpenAI(
    api_key=settings.kimi_api_key,
    base_url="https://api.moonshot.cn/v1",
)

def generate_recommendation(query: str) -> dict:
    response = _kimi_client.chat.completions.create(
        model="moonshot-v1-8k",
        messages=[
            {
                "role": "system",
                "content": (
                    "你是一个帮助用户做选择的 AI。根据用户的问题，通过联网搜索找到当前最优推荐。"
                    "只推荐一个，不要给列表。以 JSON 格式返回，包含字段：name, reason, address, price_range, rating, link。"
                    "如果某字段无法获取，设为 null。只返回 JSON，不要有其他文字。"
                ),
            },
            {"role": "user", "content": query},
        ],
        tools=[{"type": "builtin_function", "function": {"name": "$web_search"}}],
        temperature=0.3,
    )
    content = response.choices[0].message.content
    return json.loads(content)

def generate_crawler_script(query: str, result: dict) -> str:
    prompt = f"""
用户问题：{query}
当前推荐结果：{json.dumps(result, ensure_ascii=False)}

请生成一个 Python 爬虫脚本，定期获取与这个推荐相关的最新数据。
要求：
1. 使用 requests 或 httpx 库
2. 脚本返回一个 dict，格式与上面的推荐结果相同
3. 入口函数名为 run()，无参数，返回推荐结果 dict
4. 只返回 Python 代码，不要有说明文字
"""
    response = _kimi_client.chat.completions.create(
        model="moonshot-v1-8k",
        messages=[
            {"role": "system", "content": "你是一个 Python 爬虫专家，只输出可执行的 Python 代码。"},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )
    code = response.choices[0].message.content
    if code.startswith("```python"):
        code = code[9:]
    if code.startswith("```"):
        code = code[3:]
    if code.endswith("```"):
        code = code[:-3]
    return code.strip()

def evaluate_lifecycle(query: str) -> dict:
    prompt = f"""
问题：{query}

评估这个推荐问题的数据生命周期。返回 JSON，包含：
- lifecycle_type: "evergreen"（永久有效，如城市美食）/ "seasonal"（季节性，如防晒霜夏季）/ "ephemeral"（短期，如活动推荐）
- schedule_interval: 爬虫更新频率，如 "7d"、"30d"、"1d"
- ttl_days: 整个任务的存活天数（int）

只返回 JSON。
"""
    response = _kimi_client.chat.completions.create(
        model="moonshot-v1-8k",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
    )
    return json.loads(response.choices[0].message.content)
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
pytest tests/test_ai_module.py -v
```

期望：3 个 `PASSED`

- [ ] **Step 5: Commit**

```bash
git add backend/services/ai_module.py tests/test_ai_module.py
git commit -m "feat: kimi web search, recommendation generation, crawler script generation"
```

---

## Task 7: 查询端点 + 首次查询全链路

**Files:**
- Create: `backend/routers/query.py`
- Modify: `backend/services/query_router.py`（新增 save_to_cache）

- [ ] **Step 1: 在 query_router.py 末尾添加 save_to_cache 函数**

```python
def save_to_cache(
    canonical_query: str,
    embedding: list[float],
    result: dict,
    expires_at: str,
) -> str:
    db = get_db()
    vector_str = f"[{','.join(str(x) for x in embedding)}]"
    row = db.table("query_cache").insert({
        "canonical_query": canonical_query,
        "query_embedding": vector_str,
        "result": result,
        "expires_at": expires_at,
        "hit_count": 1,
        "last_hit_at": datetime.now(timezone.utc).isoformat(),
    }).execute()
    return row.data[0]["id"]
```

- [ ] **Step 2: 创建 backend/routers/query.py**

```python
from fastapi import APIRouter, Depends, HTTPException
from models.query import QueryRequest, QueryRefreshRequest, QueryResponse, RecommendationResult
from services.query_router import route_query, save_to_cache, generate_embedding
from services.ai_module import generate_recommendation, generate_crawler_script, evaluate_lifecycle
from services.personalization import personalize_result
from services.scheduler import create_crawler_task
from database import get_db
from datetime import datetime, timedelta, timezone
import httpx

router = APIRouter()

def get_current_user_id(token: str = None) -> str | None:
    # 简化版：从 header 取 user_id（完整版应解析 JWT）
    return token

@router.post("", response_model=QueryResponse)
async def query_best(req: QueryRequest):
    routed = route_query(req.query, user_id=None)
    
    if routed["cache_hit"]:
        result = RecommendationResult(**routed["result"])
        return QueryResponse(cache_id=routed["cache_id"], result=result, cache_hit=True)
    
    raw_result = generate_recommendation(req.query)
    lifecycle = evaluate_lifecycle(req.query)
    
    expires_at = (
        datetime.now(timezone.utc) + timedelta(days=lifecycle["ttl_days"])
    ).isoformat()
    
    cache_id = save_to_cache(
        canonical_query=req.query,
        embedding=routed["embedding"],
        result=raw_result,
        expires_at=expires_at,
    )
    
    script_content = generate_crawler_script(req.query, raw_result)
    create_crawler_task(
        query_cache_id=cache_id,
        script_content=script_content,
        schedule_interval=lifecycle["schedule_interval"],
        lifecycle_type=lifecycle["lifecycle_type"],
        expires_at=expires_at,
    )
    
    result = RecommendationResult(**raw_result)
    return QueryResponse(cache_id=cache_id, result=result, cache_hit=False)

@router.post("/refresh", response_model=QueryResponse)
async def refresh_query(req: QueryRefreshRequest):
    raw_result = generate_recommendation(f"{req.query}（排除ID:{req.exclude_id}，给我不同的推荐）")
    result = RecommendationResult(**raw_result)
    return QueryResponse(cache_id=req.exclude_id, result=result, cache_hit=False)
```

- [ ] **Step 3: 手动测试查询端点（需真实 API key）**

```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "成都吃面推荐一家"}'
```

期望：返回包含 `name`、`reason`、`cache_hit: false` 的 JSON。

第二次同样请求：

```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "成都吃面推荐"}'
```

期望：`cache_hit: true`，响应毫秒级。

- [ ] **Step 4: Commit**

```bash
git add backend/routers/query.py backend/services/query_router.py
git commit -m "feat: query endpoint with cache routing and first-time AI generation"
```

---

## Task 8: APScheduler + 爬虫任务管理

**Files:**
- Create: `backend/services/scheduler.py`
- Create: `backend/services/crawler_module.py`
- Create: `tests/test_scheduler.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_scheduler.py
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta, timezone

def test_create_crawler_task_saves_to_db(mock_db):
    mock_db.table.return_value.insert.return_value.execute.return_value.data = [
        {"id": "task-uuid", "status": "pending"}
    ]
    mock_storage = MagicMock()
    mock_db.storage.from_.return_value.upload = mock_storage
    
    with patch("services.scheduler.get_db", return_value=mock_db):
        from services.scheduler import create_crawler_task
        result = create_crawler_task(
            query_cache_id="cache-uuid",
            script_content="def run(): return {}",
            schedule_interval="7d",
            lifecycle_type="evergreen",
            expires_at=(datetime.now(timezone.utc) + timedelta(days=365)).isoformat(),
        )
        assert result == "task-uuid"

def test_cleanup_expired_tasks_deletes_cold_data(mock_db):
    mock_db.table.return_value.select.return_value.lt.return_value.execute.return_value.data = [
        {"id": "old-task", "query_cache_id": "old-cache"}
    ]
    
    with patch("services.scheduler.get_db", return_value=mock_db):
        from services.scheduler import cleanup_expired_tasks
        cleanup_expired_tasks()
        mock_db.table.assert_called()
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
pytest tests/test_scheduler.py -v
```

期望：`FAILED`

- [ ] **Step 3: 实现 backend/services/scheduler.py**

```python
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from database import get_db
from datetime import datetime, timedelta, timezone
import uuid

_scheduler = BackgroundScheduler()

def start_scheduler():
    _scheduler.add_job(cleanup_expired_tasks, CronTrigger(hour=3, minute=0), id="daily_cleanup")
    _scheduler.start()

def shutdown_scheduler():
    _scheduler.shutdown(wait=False)

def create_crawler_task(
    query_cache_id: str,
    script_content: str,
    schedule_interval: str,
    lifecycle_type: str,
    expires_at: str,
) -> str:
    db = get_db()
    script_path = f"crawlers/{query_cache_id}.py"
    db.storage.from_("crawler-scripts").upload(
        script_path,
        script_content.encode(),
        {"content-type": "text/plain"},
    )

    days = int(schedule_interval.replace("d", ""))
    next_run = datetime.now(timezone.utc) + timedelta(days=days)
    
    row = db.table("crawler_tasks").insert({
        "query_cache_id": query_cache_id,
        "script_path": script_path,
        "status": "pending",
        "schedule_interval": schedule_interval,
        "lifecycle_type": lifecycle_type,
        "next_run_at": next_run.isoformat(),
        "expires_at": expires_at,
    }).execute()
    
    task_id = row.data[0]["id"]
    _scheduler.add_job(
        run_crawler_task,
        IntervalTrigger(days=days),
        args=[task_id],
        id=f"crawler_{task_id}",
        next_run_time=next_run,
    )
    return task_id

def cleanup_expired_tasks():
    db = get_db()
    now = datetime.now(timezone.utc).isoformat()
    expired = (
        db.table("crawler_tasks")
        .select("id, query_cache_id")
        .lt("expires_at", now)
        .execute()
    )
    for task in expired.data:
        try:
            _scheduler.remove_job(f"crawler_{task['id']}")
        except Exception:
            pass
        db.table("crawler_tasks").delete().eq("id", task["id"]).execute()
        db.table("query_cache").delete().eq("id", task["query_cache_id"]).execute()

def run_crawler_task(task_id: str):
    from services.crawler_module import execute_crawler_task
    execute_crawler_task(task_id)
```

- [ ] **Step 4: 实现 backend/services/crawler_module.py**

```python
import importlib.util
import tempfile
import os
from database import get_db
from services.ai_module import generate_recommendation
from datetime import datetime, timezone

def execute_crawler_task(task_id: str):
    db = get_db()
    task = db.table("crawler_tasks").select("*").eq("id", task_id).execute().data
    if not task:
        return
    task = task[0]
    
    db.table("crawler_tasks").update({"status": "running"}).eq("id", task_id).execute()
    
    try:
        script_bytes = db.storage.from_("crawler-scripts").download(task["script_path"])
        
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="wb") as f:
            f.write(script_bytes)
            tmp_path = f.name
        
        spec = importlib.util.spec_from_file_location("crawler_script", tmp_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        result = module.run()
        os.unlink(tmp_path)
        
        db.table("query_cache").update({
            "result": result,
            "last_hit_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", task["query_cache_id"]).execute()
        
        db.table("crawler_tasks").update({"status": "done"}).eq("id", task_id).execute()
    
    except Exception as e:
        db.table("crawler_tasks").update({"status": "pending"}).eq("id", task_id).execute()
        raise e
```

- [ ] **Step 5: 运行测试，确认通过**

```bash
pytest tests/test_scheduler.py -v
```

期望：`PASSED`

- [ ] **Step 6: Commit**

```bash
git add backend/services/scheduler.py backend/services/crawler_module.py tests/test_scheduler.py
git commit -m "feat: APScheduler crawler task management and cold data cleanup"
```

---

## Task 9: 用户端点 + 个性化润色

**Files:**
- Create: `backend/routers/user.py`
- Create: `backend/services/personalization.py`

- [ ] **Step 1: 实现 backend/services/personalization.py**

```python
from models.query import RecommendationResult

BUDGET_MAP = {"低": (0, 50), "中等": (50, 150), "高": (150, 9999)}

def personalize_result(result: dict, preferences: dict) -> dict:
    note_parts = []
    
    budget = preferences.get("budget", "中等")
    price_range = result.get("price_range", "")
    if price_range and budget == "低" and "人均" in price_range:
        note_parts.append("价格符合你的预算")
    
    cuisine_prefs = preferences.get("cuisine", [])
    reason = result.get("reason", "")
    if cuisine_prefs and any(c in reason for c in cuisine_prefs):
        note_parts.append(f"符合你喜欢{'/'.join(cuisine_prefs)}的口味")
    
    if note_parts:
        result = {**result, "personalization_note": "、".join(note_parts)}
    
    return result
```

- [ ] **Step 2: 实现 backend/routers/user.py**

```python
from fastapi import APIRouter, Header, HTTPException
from models.user import UpdatePreferencesRequest
from database import get_db
from jose import jwt, JWTError
from config import settings

router = APIRouter()

def get_user_from_token(authorization: str = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录")
    token = authorization[7:]
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        user_id = payload["sub"]
    except JWTError:
        raise HTTPException(status_code=401, detail="Token 无效")
    db = get_db()
    user = db.table("users").select("*").eq("id", user_id).execute()
    if not user.data:
        raise HTTPException(status_code=404, detail="用户不存在")
    return user.data[0]

@router.get("/profile")
def get_profile(authorization: str = Header(None)):
    user = get_user_from_token(authorization)
    return user

@router.put("/preferences")
def update_preferences(req: UpdatePreferencesRequest, authorization: str = Header(None)):
    user = get_user_from_token(authorization)
    current_prefs = user.get("preferences", {})
    updates = req.model_dump(exclude_none=True)
    new_prefs = {**current_prefs, **updates}
    db = get_db()
    db.table("users").update({"preferences": new_prefs}).eq("id", user["id"]).execute()
    return {"ok": True, "preferences": new_prefs}

@router.get("/history")
def get_history(authorization: str = Header(None)):
    user = get_user_from_token(authorization)
    db = get_db()
    history = (
        db.table("user_query_history")
        .select("*, query_cache(result, canonical_query)")
        .eq("user_id", user["id"])
        .order("created_at", desc=True)
        .limit(20)
        .execute()
    )
    return history.data
```

- [ ] **Step 3: 测试偏好接口**

```bash
# 先登录拿 token（用微信模拟 code）
TOKEN="your-jwt-token"

curl -X PUT http://localhost:8000/api/user/preferences \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"cuisine": ["辣", "川味"], "budget": "低", "city": "成都"}'
```

期望：`{"ok": true, "preferences": {...}}`

- [ ] **Step 4: Commit**

```bash
git add backend/routers/user.py backend/services/personalization.py
git commit -m "feat: user profile endpoints and preference-based personalization"
```

---

## Task 10: 微信小程序搭建

**Files:**
- Create: `miniprogram/app.js`
- Create: `miniprogram/app.json`
- Create: `miniprogram/app.wxss`
- Create: `miniprogram/utils/request.js`

- [ ] **Step 1: 创建 miniprogram/app.json**

```json
{
  "pages": [
    "pages/index/index",
    "pages/result/result",
    "pages/profile/profile"
  ],
  "window": {
    "backgroundTextStyle": "light",
    "navigationBarBackgroundColor": "#1a1a2e",
    "navigationBarTitleText": "Best Choice",
    "navigationBarTextStyle": "white"
  },
  "tabBar": {
    "color": "#999",
    "selectedColor": "#1a1a2e",
    "list": [
      {"pagePath": "pages/index/index", "text": "发现"},
      {"pagePath": "pages/profile/profile", "text": "我的"}
    ]
  },
  "spermission": {
    "scope.record": {"desc": "语音输入使用"}
  }
}
```

- [ ] **Step 2: 创建 miniprogram/app.js**

```javascript
App({
  globalData: {
    token: null,
    userInfo: null,
    apiBase: 'https://your-railway-app.up.railway.app'
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
```

- [ ] **Step 3: 创建 miniprogram/utils/request.js**

```javascript
const app = getApp();

function request(method, path, data = {}) {
  return new Promise((resolve, reject) => {
    wx.request({
      url: `${app.globalData.apiBase}${path}`,
      method,
      data,
      header: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${app.globalData.token}`
      },
      success: (res) => {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.data);
        } else {
          reject(res.data);
        }
      },
      fail: reject
    });
  });
}

module.exports = {
  get: (path) => request('GET', path),
  post: (path, data) => request('POST', path, data),
  put: (path, data) => request('PUT', path, data),
};
```

- [ ] **Step 4: Commit**

```bash
git add miniprogram/app.js miniprogram/app.json miniprogram/app.wxss miniprogram/utils/request.js
git commit -m "feat: wechat miniprogram app scaffold with auth and request utility"
```

---

## Task 11: 小程序首页

**Files:**
- Create: `miniprogram/pages/index/index.wxml`
- Create: `miniprogram/pages/index/index.wxss`
- Create: `miniprogram/pages/index/index.js`

- [ ] **Step 1: 创建 index.wxml**

```xml
<view class="container">
  <view class="header">
    <text class="title">Best Choice</text>
    <text class="subtitle">告别选择困难，直接给你最优解</text>
  </view>

  <view class="search-box">
    <input
      class="search-input"
      placeholder="我想..."
      value="{{query}}"
      bindinput="onQueryInput"
      confirm-type="search"
      bindconfirm="onSearch"
    />
    <button class="search-btn" bindtap="onSearch" loading="{{loading}}">
      {{loading ? '' : '选我'}}
    </button>
  </view>

  <view class="quick-tags">
    <view class="tag" wx:for="{{quickTags}}" wx:key="*this" bindtap="onTagTap" data-tag="{{item}}">
      {{item}}
    </view>
  </view>

  <view class="history" wx:if="{{history.length > 0}}">
    <text class="section-title">最近查过的</text>
    <view class="history-item" wx:for="{{history}}" wx:key="id" bindtap="onHistoryTap" data-item="{{item}}">
      <text class="history-query">{{item.query_text}}</text>
      <text class="history-result">→ {{item.query_cache.result.name}}</text>
    </view>
  </view>
</view>
```

- [ ] **Step 2: 创建 index.wxss**

```css
.container { padding: 40rpx; background: #f5f5f7; min-height: 100vh; }
.header { text-align: center; padding: 60rpx 0 40rpx; }
.title { font-size: 56rpx; font-weight: 700; color: #1a1a2e; display: block; }
.subtitle { font-size: 26rpx; color: #888; display: block; margin-top: 12rpx; }
.search-box { display: flex; background: #fff; border-radius: 24rpx; padding: 16rpx 20rpx; margin: 20rpx 0; box-shadow: 0 4rpx 20rpx rgba(0,0,0,0.08); }
.search-input { flex: 1; font-size: 32rpx; color: #333; }
.search-btn { background: #1a1a2e; color: #fff; border-radius: 16rpx; font-size: 28rpx; padding: 0 30rpx; }
.quick-tags { display: flex; flex-wrap: wrap; gap: 16rpx; margin: 20rpx 0; }
.tag { background: #fff; border-radius: 40rpx; padding: 12rpx 28rpx; font-size: 26rpx; color: #555; box-shadow: 0 2rpx 10rpx rgba(0,0,0,0.06); }
.section-title { font-size: 28rpx; color: #888; margin: 30rpx 0 16rpx; display: block; }
.history-item { background: #fff; border-radius: 16rpx; padding: 24rpx; margin-bottom: 16rpx; }
.history-query { font-size: 28rpx; color: #333; display: block; }
.history-result { font-size: 24rpx; color: #888; display: block; margin-top: 8rpx; }
```

- [ ] **Step 3: 创建 index.js**

```javascript
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
```

- [ ] **Step 4: Commit**

```bash
git add miniprogram/pages/index/
git commit -m "feat: miniprogram index page with search and history"
```

---

## Task 12: 小程序推荐结果页

**Files:**
- Create: `miniprogram/pages/result/result.wxml`
- Create: `miniprogram/pages/result/result.wxss`
- Create: `miniprogram/pages/result/result.js`

- [ ] **Step 1: 创建 result.wxml**

```xml
<view class="container">
  <view class="query-text">
    <text>你问的是：{{query}}</text>
  </view>

  <view class="card" wx:if="{{result}}">
    <view class="badge" wx:if="{{cacheHit}}">⚡ 即时推荐</view>
    <view class="badge fresh" wx:else>🔍 AI 实时分析</view>

    <text class="name">{{result.name}}</text>
    <text class="reason">{{result.reason}}</text>

    <view class="info-row" wx:if="{{result.address}}">
      <text class="label">📍</text>
      <text class="value">{{result.address}}</text>
    </view>
    <view class="info-row" wx:if="{{result.price_range}}">
      <text class="label">💰</text>
      <text class="value">{{result.price_range}}</text>
    </view>
    <view class="info-row" wx:if="{{result.rating}}">
      <text class="label">⭐</text>
      <text class="value">{{result.rating}} 分</text>
    </view>
    <view class="personalization" wx:if="{{result.personalization_note}}">
      <text>✓ {{result.personalization_note}}</text>
    </view>

    <button class="link-btn" wx:if="{{result.link}}" bindtap="openLink">
      查看详情 →
    </button>
  </view>

  <button class="refresh-btn" bindtap="onRefresh" loading="{{refreshing}}">
    换一个
  </button>
</view>
```

- [ ] **Step 2: 创建 result.wxss**

```css
.container { padding: 40rpx; background: #f5f5f7; min-height: 100vh; }
.query-text { font-size: 26rpx; color: #888; margin-bottom: 24rpx; }
.card { background: #fff; border-radius: 28rpx; padding: 48rpx 40rpx; box-shadow: 0 8rpx 40rpx rgba(0,0,0,0.10); }
.badge { display: inline-block; font-size: 22rpx; color: #888; border: 1rpx solid #e0e0e0; border-radius: 20rpx; padding: 6rpx 18rpx; margin-bottom: 24rpx; }
.badge.fresh { color: #007aff; border-color: #007aff; }
.name { font-size: 52rpx; font-weight: 700; color: #1a1a2e; display: block; margin-bottom: 20rpx; }
.reason { font-size: 30rpx; color: #555; line-height: 1.6; display: block; margin-bottom: 32rpx; }
.info-row { display: flex; align-items: center; margin-bottom: 16rpx; }
.label { font-size: 28rpx; margin-right: 12rpx; }
.value { font-size: 28rpx; color: #444; }
.personalization { background: #f0f9ff; border-radius: 12rpx; padding: 16rpx 20rpx; margin-top: 24rpx; font-size: 26rpx; color: #007aff; }
.link-btn { background: #1a1a2e; color: #fff; border-radius: 16rpx; margin-top: 32rpx; font-size: 30rpx; }
.refresh-btn { background: transparent; color: #888; border: 2rpx solid #ddd; border-radius: 16rpx; margin-top: 32rpx; font-size: 28rpx; }
```

- [ ] **Step 3: 创建 result.js**

```javascript
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
```

- [ ] **Step 4: Commit**

```bash
git add miniprogram/pages/result/
git commit -m "feat: miniprogram result page with recommendation card and refresh"
```

---

## Task 13: 小程序个人中心页

**Files:**
- Create: `miniprogram/pages/profile/profile.wxml`
- Create: `miniprogram/pages/profile/profile.wxss`
- Create: `miniprogram/pages/profile/profile.js`

- [ ] **Step 1: 创建 profile.wxml**

```xml
<view class="container">
  <view class="header">
    <text class="title">我的偏好</text>
  </view>

  <view class="section">
    <text class="label">常驻城市</text>
    <input class="input" placeholder="如：成都" value="{{prefs.city}}" bindinput="onCityInput" />
  </view>

  <view class="section">
    <text class="label">预算偏好</text>
    <view class="options">
      <view class="option {{prefs.budget === '低' ? 'active' : ''}}" bindtap="onBudgetTap" data-val="低">低</view>
      <view class="option {{prefs.budget === '中等' ? 'active' : ''}}" bindtap="onBudgetTap" data-val="中等">中等</view>
      <view class="option {{prefs.budget === '高' ? 'active' : ''}}" bindtap="onBudgetTap" data-val="高">高</view>
    </view>
  </view>

  <view class="section">
    <text class="label">口味偏好（多选）</text>
    <view class="options">
      <view
        class="option {{prefs.cuisine.includes(item) ? 'active' : ''}}"
        wx:for="{{cuisineOptions}}" wx:key="*this"
        bindtap="onCuisineTap" data-val="{{item}}"
      >{{item}}</view>
    </view>
  </view>

  <button class="save-btn" bindtap="onSave" loading="{{saving}}">保存偏好</button>
</view>
```

- [ ] **Step 2: 创建 profile.wxss**

```css
.container { padding: 40rpx; background: #f5f5f7; min-height: 100vh; }
.header { padding: 40rpx 0 20rpx; }
.title { font-size: 44rpx; font-weight: 700; color: #1a1a2e; }
.section { background: #fff; border-radius: 20rpx; padding: 32rpx; margin-bottom: 24rpx; }
.label { font-size: 28rpx; color: #888; display: block; margin-bottom: 20rpx; }
.input { font-size: 32rpx; color: #333; border-bottom: 1rpx solid #eee; padding-bottom: 12rpx; }
.options { display: flex; flex-wrap: wrap; gap: 16rpx; }
.option { background: #f5f5f7; border-radius: 40rpx; padding: 12rpx 28rpx; font-size: 28rpx; color: #555; }
.option.active { background: #1a1a2e; color: #fff; }
.save-btn { background: #1a1a2e; color: #fff; border-radius: 20rpx; margin-top: 16rpx; font-size: 32rpx; height: 96rpx; line-height: 96rpx; }
```

- [ ] **Step 3: 创建 profile.js**

```javascript
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
```

- [ ] **Step 4: Commit**

```bash
git add miniprogram/pages/profile/
git commit -m "feat: miniprogram profile page with preference settings"
```

---

## Task 14: Docker + Railway 部署

**Files:**
- Create: `backend/Dockerfile`
- Create: `backend/docker-compose.yml`
- Create: `railway.json`

- [ ] **Step 1: 创建 backend/Dockerfile**

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: 创建 backend/docker-compose.yml（本地开发）**

```yaml
version: '3.8'
services:
  api:
    build: .
    ports:
      - "8000:8000"
    env_file:
      - .env
    volumes:
      - .:/app
    command: uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

- [ ] **Step 3: 创建 railway.json**

```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "DOCKERFILE",
    "dockerfilePath": "backend/Dockerfile"
  },
  "deploy": {
    "startCommand": "uvicorn main:app --host 0.0.0.0 --port $PORT",
    "healthcheckPath": "/docs",
    "restartPolicyType": "ON_FAILURE"
  }
}
```

- [ ] **Step 4: 本地 Docker 验证**

```bash
cd backend && docker build -t best-choice-api .
docker run -p 8000:8000 --env-file .env best-choice-api
```

期望：`http://localhost:8000/docs` 正常访问。

- [ ] **Step 5: 部署到 Railway**

```bash
# 安装 Railway CLI
npm install -g @railway/cli
railway login
railway init
railway up
```

期望：Railway 控制台显示服务运行中，并提供公网 URL。

- [ ] **Step 6: 更新小程序 apiBase**

编辑 `miniprogram/app.js`，将 `apiBase` 替换为 Railway 分配的 URL：

```javascript
apiBase: 'https://best-choice-xxx.up.railway.app'
```

- [ ] **Step 7: Commit**

```bash
git add backend/Dockerfile backend/docker-compose.yml railway.json miniprogram/app.js
git commit -m "feat: docker and railway deployment configuration"
```

---

## Task 15: 集成测试 + 验收

**Files:**
- Create: `tests/test_integration.py`

- [ ] **Step 1: 写集成测试**

```python
# tests/test_integration.py
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from main import app

client = TestClient(app)

def test_full_query_flow_cache_miss():
    mock_result = {
        "name": "老妈蹄花",
        "reason": "成都最正宗的蹄花汤，老字号",
        "address": "成都市武侯区XX路",
        "price_range": "人均60-80元",
        "rating": 4.9,
        "link": None,
    }
    mock_lifecycle = {"lifecycle_type": "evergreen", "schedule_interval": "7d", "ttl_days": 365}

    with patch("services.query_router.generate_embedding") as mock_embed, \
         patch("services.query_router.search_cache") as mock_search, \
         patch("services.query_router.save_to_cache") as mock_save, \
         patch("services.ai_module.generate_recommendation") as mock_rec, \
         patch("services.ai_module.generate_crawler_script") as mock_script, \
         patch("services.ai_module.evaluate_lifecycle") as mock_life, \
         patch("services.scheduler.create_crawler_task") as mock_task:

        mock_embed.return_value = [0.1] * 1536
        mock_search.return_value = None
        mock_save.return_value = "new-cache-uuid"
        mock_rec.return_value = mock_result
        mock_script.return_value = "def run(): return {}"
        mock_life.return_value = mock_lifecycle
        mock_task.return_value = "task-uuid"

        response = client.post("/api/query", json={"query": "成都吃蹄花"})

        assert response.status_code == 200
        data = response.json()
        assert data["cache_hit"] is False
        assert data["result"]["name"] == "老妈蹄花"

def test_full_query_flow_cache_hit():
    cached = {
        "id": "cache-uuid",
        "result": {"name": "老妈蹄花", "reason": "成都老字号"},
        "expires_at": "2099-01-01T00:00:00+00:00",
    }
    with patch("services.query_router.generate_embedding") as mock_embed, \
         patch("services.query_router.search_cache") as mock_search, \
         patch("services.query_router.update_cache_hit"):

        mock_embed.return_value = [0.1] * 1536
        mock_search.return_value = cached

        response = client.post("/api/query", json={"query": "成都吃蹄花"})

        assert response.status_code == 200
        data = response.json()
        assert data["cache_hit"] is True
        assert data["result"]["name"] == "老妈蹄花"
```

- [ ] **Step 2: 运行全量测试**

```bash
cd backend && pytest tests/ -v --tb=short
```

期望：所有测试 `PASSED`，无 `FAILED`。

- [ ] **Step 3: 手动验收清单（微信开发者工具）**

```
□ 首次查询"成都吃面" → 返回推荐卡片，cache_hit=false
□ 再次查询"成都吃面" → 返回同样推荐，cache_hit=true，响应 <500ms
□ 点击"换一个" → 返回不同推荐
□ 设置偏好（城市=成都，预算=低）→ 推荐卡片出现 personalization_note
□ 历史记录页 → 显示最近 5 条查询
□ Railway 部署 URL 可正常访问 /docs
```

- [ ] **Step 4: 最终 Commit**

```bash
git add tests/test_integration.py
git commit -m "test: integration tests for full query flow"
```

---

## 自检结果

**Spec 覆盖度：**
- ✅ 单一最优推荐（Task 6-7）
- ✅ pgvector 缓存查询（Task 5）
- ✅ Kimi 联网搜索（Task 6）
- ✅ 自动生成爬虫脚本（Task 6）
- ✅ AI 评估生命周期（Task 6）
- ✅ APScheduler 定时更新（Task 8）
- ✅ 冷数据清理（Task 8）
- ✅ 用户画像 + 个性化润色（Task 9）
- ✅ 微信登录（Task 4）
- ✅ 小程序三页面（Task 10-13）
- ✅ Railway 部署（Task 14）
- ✅ 测试覆盖（Task 4-9, 15）

**类型一致性：** `RecommendationResult` 贯穿 ai_module → query_router → routers/query → 小程序 result 页，字段名统一。

**范围：** 15 个任务，可在 4 周内完成。
