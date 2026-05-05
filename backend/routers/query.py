from fastapi import APIRouter, Header

from models.query import QueryRequest, QueryRefreshRequest, QueryResponse, RecommendationResult
from services.query_router import route_query, save_to_cache
from services.ai_module import generate_recommendation, generate_crawler_script, evaluate_lifecycle
from services.scheduler import create_crawler_task
from services.personalization import personalize_result
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import jwt, JWTError
from config import settings
from database import get_db

router = APIRouter()


def _get_user_preferences(authorization: Optional[str]) -> dict:
    """Extract user preferences from an optional Bearer token.

    Returns an empty dict if no valid token is provided (anonymous user).
    """
    if not authorization or not authorization.startswith("Bearer "):
        return {}
    token = authorization[7:]
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        user_id = payload["sub"]
    except (JWTError, KeyError):
        return {}
    db = get_db()
    user = db.table("users").select("preferences").eq("id", user_id).execute()
    if not user.data:
        return {}
    return user.data[0].get("preferences", {})


@router.post("", response_model=QueryResponse)
async def query_best(req: QueryRequest, authorization: Optional[str] = Header(None)):
    preferences = _get_user_preferences(authorization)
    user_id = None

    if authorization and authorization.startswith("Bearer "):
        try:
            payload = jwt.decode(
                authorization[7:], settings.jwt_secret, algorithms=["HS256"]
            )
            user_id = payload["sub"]
        except (JWTError, KeyError):
            pass

    routed = route_query(req.query, user_id=user_id)

    if routed["cache_hit"]:
        personalized = personalize_result(routed["result"], preferences)
        result = RecommendationResult(**personalized)
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

    personalized = personalize_result(raw_result, preferences)
    result = RecommendationResult(**personalized)
    return QueryResponse(cache_id=cache_id, result=result, cache_hit=False)


@router.post("/refresh", response_model=QueryResponse)
async def refresh_query(req: QueryRefreshRequest, authorization: Optional[str] = Header(None)):
    preferences = _get_user_preferences(authorization)
    raw_result = generate_recommendation(
        f"{req.query}（排除ID:{req.exclude_id}，给我不同的推荐）"
    )
    personalized = personalize_result(raw_result, preferences)
    result = RecommendationResult(**personalized)
    return QueryResponse(cache_id=req.exclude_id, result=result, cache_hit=False)
