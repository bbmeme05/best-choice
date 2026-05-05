def start_scheduler() -> None:
    pass


def shutdown_scheduler() -> None:
    pass


def create_crawler_task(
    query_cache_id: str,
    script_content: str,
    schedule_interval: str,
    lifecycle_type: str,
    expires_at: str,
) -> str:
    """Create a scheduled crawler task for keeping a recommendation fresh.

    Returns the task ID. Full implementation in Task 8.
    """
    raise NotImplementedError("create_crawler_task will be implemented in Task 8")
