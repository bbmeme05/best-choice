from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from database import get_db
from datetime import datetime, timedelta, timezone
import logging

_scheduler = BackgroundScheduler()
_logger = logging.getLogger(__name__)


def start_scheduler() -> None:
    """Start the background scheduler with a daily cleanup job."""
    if not _scheduler.running:
        _scheduler.add_job(
            cleanup_expired_tasks,
            CronTrigger(hour=3, minute=0),
            id="daily_cleanup",
            replace_existing=True,
        )
        _scheduler.start()
        _logger.info("Scheduler started with daily_cleanup job at 03:00")


def shutdown_scheduler() -> None:
    """Shut down the background scheduler."""
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
        _logger.info("Scheduler shut down")


def create_crawler_task(
    query_cache_id: str,
    script_content: str,
    schedule_interval: str,
    lifecycle_type: str,
    expires_at: str,
) -> str:
    """Create a scheduled crawler task for keeping a recommendation fresh.

    Uploads the crawler script to Supabase Storage, inserts a task row,
    and registers a recurring job with APScheduler.

    Returns the task ID.
    """
    db = get_db()
    script_path = f"crawlers/{query_cache_id}.py"
    db.storage.from_("crawler-scripts").upload(
        script_path,
        script_content.encode(),
        {"content-type": "text/plain"},
    )

    days = int(schedule_interval.replace("d", ""))
    next_run = datetime.now(timezone.utc) + timedelta(days=days)

    row = (
        db.table("crawler_tasks")
        .insert(
            {
                "query_cache_id": query_cache_id,
                "script_path": script_path,
                "status": "pending",
                "schedule_interval": schedule_interval,
                "lifecycle_type": lifecycle_type,
                "next_run_at": next_run.isoformat(),
                "expires_at": expires_at,
            }
        )
        .execute()
    )

    task_id = row.data[0]["id"]
    _scheduler.add_job(
        run_crawler_task,
        IntervalTrigger(days=days),
        args=[task_id],
        id=f"crawler_{task_id}",
        next_run_time=next_run,
        replace_existing=True,
    )
    _logger.info("Created crawler task %s, next run at %s", task_id, next_run)
    return task_id


def cleanup_expired_tasks() -> None:
    """Remove expired crawler tasks and their associated cache entries."""
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
    if expired.data:
        _logger.info("Cleaned up %d expired task(s)", len(expired.data))


def run_crawler_task(task_id: str) -> None:
    """Execute a crawler task by delegating to the crawler module."""
    from services.crawler_module import execute_crawler_task

    execute_crawler_task(task_id)
