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
