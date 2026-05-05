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
