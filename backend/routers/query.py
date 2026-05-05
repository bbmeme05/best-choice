from fastapi import APIRouter

from models.query import QueryRequest, QueryRefreshRequest, QueryResponse, RecommendationResult
from services.query_router import route_query, save_to_cache
from services.ai_module import generate_recommendation, generate_crawler_script, evaluate_lifecycle
from services.scheduler import create_crawler_task
# from services.personalization import personalize_result  # Task 9
from datetime import datetime, timedelta, timezone

router = APIRouter()


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
    raw_result = generate_recommendation(
        f"{req.query}（排除ID:{req.exclude_id}，给我不同的推荐）"
    )
    result = RecommendationResult(**raw_result)
    return QueryResponse(cache_id=req.exclude_id, result=result, cache_hit=False)
