import importlib.util
import logging
import os
import tempfile

from database import get_db
from datetime import datetime, timezone

_logger = logging.getLogger(__name__)


def execute_crawler_task(task_id: str) -> None:
    """Download, execute, and store results for a crawler task.

    Downloads the crawler script from Supabase Storage, executes it in
    a temporary file, updates the query cache with the result, and marks
    the task as done. On failure, the task is reset to pending status.
    """
    db = get_db()
    task_rows = (
        db.table("crawler_tasks").select("*").eq("id", task_id).execute().data
    )
    if not task_rows:
        _logger.warning("Crawler task %s not found, skipping", task_id)
        return
    task = task_rows[0]

    db.table("crawler_tasks").update({"status": "running"}).eq(
        "id", task_id
    ).execute()

    try:
        script_bytes = db.storage.from_("crawler-scripts").download(
            task["script_path"]
        )

        tmp_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                suffix=".py", delete=False, mode="wb"
            ) as f:
                f.write(script_bytes)
                tmp_path = f.name

            spec = importlib.util.spec_from_file_location("crawler_script", tmp_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)  # type: ignore[union-attr]
            result = module.run()  # type: ignore[union-attr]
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

        db.table("query_cache").update(
            {
                "result": result,
                "last_hit_at": datetime.now(timezone.utc).isoformat(),
            }
        ).eq("id", task["query_cache_id"]).execute()

        db.table("crawler_tasks").update({"status": "done"}).eq(
            "id", task_id
        ).execute()
        _logger.info("Crawler task %s completed successfully", task_id)

    except Exception:
        db.table("crawler_tasks").update({"status": "pending"}).eq(
            "id", task_id
        ).execute()
        _logger.exception("Crawler task %s failed, reset to pending", task_id)
        raise
