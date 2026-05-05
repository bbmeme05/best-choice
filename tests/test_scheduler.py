import pytest
from unittest.mock import patch, MagicMock, call
from datetime import datetime, timedelta, timezone


def test_create_crawler_task_saves_to_db(mock_db):
    """create_crawler_task should insert a row, upload script, and return the task ID."""
    mock_db.table.return_value.insert.return_value.execute.return_value.data = [
        {"id": "task-uuid", "status": "pending"}
    ]
    mock_storage = MagicMock()
    mock_db.storage.from_.return_value.upload = mock_storage

    with patch("services.scheduler.get_db", return_value=mock_db), \
         patch("services.scheduler._scheduler") as mock_sched:
        from services.scheduler import create_crawler_task
        result = create_crawler_task(
            query_cache_id="cache-uuid",
            script_content="def run(): return {}",
            schedule_interval="7d",
            lifecycle_type="evergreen",
            expires_at=(datetime.now(timezone.utc) + timedelta(days=365)).isoformat(),
        )

    assert result == "task-uuid"
    mock_db.storage.from_.assert_called_with("crawler-scripts")
    mock_storage.assert_called_once()
    mock_db.table.assert_called_with("crawler_tasks")
    mock_sched.add_job.assert_called_once()


def test_create_crawler_task_registers_scheduler_job(mock_db):
    """create_crawler_task should register an IntervalTrigger job with APScheduler."""
    mock_db.table.return_value.insert.return_value.execute.return_value.data = [
        {"id": "task-abc", "status": "pending"}
    ]

    with patch("services.scheduler.get_db", return_value=mock_db), \
         patch("services.scheduler._scheduler") as mock_sched:
        from services.scheduler import create_crawler_task
        create_crawler_task(
            query_cache_id="cache-abc",
            script_content="def run(): pass",
            schedule_interval="30d",
            lifecycle_type="seasonal",
            expires_at=(datetime.now(timezone.utc) + timedelta(days=180)).isoformat(),
        )

    add_call = mock_sched.add_job.call_args
    assert add_call[0][0].__name__ == "run_crawler_task"
    assert add_call[1]["args"] == ["task-abc"]
    assert add_call[1]["id"] == "crawler_task-abc"


def test_cleanup_expired_tasks_deletes_cold_data(mock_db):
    """cleanup_expired_tasks should find expired tasks and delete them + their cache."""
    mock_db.table.return_value.select.return_value.lt.return_value.execute.return_value.data = [
        {"id": "old-task", "query_cache_id": "old-cache"},
    ]

    with patch("services.scheduler.get_db", return_value=mock_db), \
         patch("services.scheduler._scheduler") as mock_sched:
        from services.scheduler import cleanup_expired_tasks
        cleanup_expired_tasks()

    mock_sched.remove_job.assert_called_with("crawler_old-task")
    # Should have called delete for both crawler_tasks and query_cache
    assert mock_db.table.call_count >= 2


def test_cleanup_expired_tasks_handles_missing_scheduler_job(mock_db):
    """cleanup_expired_tasks should not fail if the scheduler job is already gone."""
    mock_db.table.return_value.select.return_value.lt.return_value.execute.return_value.data = [
        {"id": "old-task-2", "query_cache_id": "old-cache-2"},
    ]

    with patch("services.scheduler.get_db", return_value=mock_db), \
         patch("services.scheduler._scheduler") as mock_sched:
        mock_sched.remove_job.side_effect = Exception("Job not found")
        from services.scheduler import cleanup_expired_tasks
        # Should not raise
        cleanup_expired_tasks()

    # Deletions should still happen even though remove_job failed
    assert mock_db.table.call_count >= 2


def test_cleanup_expired_tasks_no_expired(mock_db):
    """cleanup_expired_tasks should be a no-op when there are no expired tasks."""
    mock_db.table.return_value.select.return_value.lt.return_value.execute.return_value.data = []

    with patch("services.scheduler.get_db", return_value=mock_db), \
         patch("services.scheduler._scheduler") as mock_sched:
        from services.scheduler import cleanup_expired_tasks
        cleanup_expired_tasks()

    mock_sched.remove_job.assert_not_called()


def test_start_scheduler_registers_cleanup_job():
    """start_scheduler should add the daily_cleanup cron job and start the scheduler."""
    with patch("services.scheduler._scheduler") as mock_sched:
        mock_sched.running = False
        from services.scheduler import start_scheduler
        start_scheduler()

    mock_sched.add_job.assert_called_once()
    mock_sched.start.assert_called_once()
    add_call = mock_sched.add_job.call_args
    assert add_call[1]["id"] == "daily_cleanup"
    assert add_call[1]["replace_existing"] is True


def test_shutdown_scheduler():
    """shutdown_scheduler should call shutdown on the scheduler."""
    with patch("services.scheduler._scheduler") as mock_sched:
        mock_sched.running = True
        from services.scheduler import shutdown_scheduler
        shutdown_scheduler()

    mock_sched.shutdown.assert_called_once_with(wait=False)


def test_run_crawler_task_delegates(mock_db):
    """run_crawler_task should delegate to crawler_module.execute_crawler_task."""
    with patch("services.crawler_module.execute_crawler_task") as mock_exec:
        from services.scheduler import run_crawler_task
        run_crawler_task("task-123")

    mock_exec.assert_called_once_with("task-123")
