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
