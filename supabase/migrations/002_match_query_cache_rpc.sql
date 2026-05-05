-- pgvector cosine-similarity match function for query_cache
-- Called via Supabase RPC: db.rpc("match_query_cache", {...})

create or replace function match_query_cache(
  query_embedding vector(1536),
  match_threshold float,
  match_count int
)
returns table (
  id uuid,
  canonical_query text,
  result jsonb,
  hit_count int,
  last_hit_at timestamptz,
  expires_at timestamptz,
  created_at timestamptz
)
language sql stable
as $$
  select
    id,
    canonical_query,
    result,
    hit_count,
    last_hit_at,
    expires_at,
    created_at
  from query_cache
  where query_embedding <=> query_embedding < 1 - match_threshold
  order by query_embedding <=> query_embedding
  limit match_count;
$$;
