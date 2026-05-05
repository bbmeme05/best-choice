from datetime import datetime, timezone

from openai import OpenAI

from config import settings
from database import get_db

_openai = OpenAI(api_key=settings.openai_api_key)


def generate_embedding(text: str) -> list[float]:
    """Generate an embedding vector for the given text using OpenAI."""
    response = _openai.embeddings.create(
        model="text-embedding-ada-002",
        input=text,
    )
    return response.data[0].embedding


def search_cache(embedding: list[float], threshold: float = 0.85) -> dict | None:
    """Search the pgvector cache for a similar query via Supabase RPC."""
    db = get_db()
    vector_str = f"[{','.join(str(x) for x in embedding)}]"
    result = db.rpc(
        "match_query_cache",
        {
            "query_embedding": vector_str,
            "match_threshold": threshold,
            "match_count": 1,
        },
    ).execute()
    if not result.data:
        return None
    row = result.data[0]
    expires_at = datetime.fromisoformat(row["expires_at"])
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        return None
    return row


def update_cache_hit(cache_id: str) -> None:
    """Increment hit_count and update last_hit_at for a cached query."""
    db = get_db()
    table = db.table("query_cache")

    # Read current hit_count, then write incremented value (avoids RPC dependency)
    current = (
        table.select("hit_count")
        .eq("id", cache_id)
        .single()
        .execute()
    )
    new_count = current.data["hit_count"] + 1

    table.update(
        {
            "hit_count": new_count,
            "last_hit_at": datetime.now(timezone.utc).isoformat(),
        }
    ).eq("id", cache_id).execute()


def route_query(query: str, user_id: str) -> dict:
    """Route a user query: generate embedding, check cache, return result."""
    embedding = generate_embedding(query)
    cached = search_cache(embedding)
    if cached:
        update_cache_hit(cached["id"])
        return {
            "cache_hit": True,
            "cache_id": cached["id"],
            "result": cached["result"],
            "embedding": embedding,
        }
    return {
        "cache_hit": False,
        "cache_id": None,
        "result": None,
        "embedding": embedding,
    }
