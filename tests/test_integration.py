# tests/test_integration.py
"""Integration tests for the full query flow through the FastAPI endpoints."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch


def test_full_query_flow_cache_miss():
    """Test the full query flow when there is no cache hit.

    Verifies that a POST to /api/query goes through embedding generation,
    cache miss detection, AI recommendation, lifecycle evaluation,
    cache saving, crawler script generation, and task creation,
    then returns the recommendation.
    """
    mock_result = {
        "name": "老妈蹄花",
        "reason": "成都最正宗的蹄花汤，老字号",
        "address": "成都市武侯区XX路",
        "price_range": "人均60-80元",
        "rating": 4.9,
        "link": None,
    }
    mock_lifecycle = {
        "lifecycle_type": "evergreen",
        "schedule_interval": "7d",
        "ttl_days": 365,
    }

    with patch("main.start_scheduler"), \
         patch("main.shutdown_scheduler"), \
         patch("services.query_router.generate_embedding") as mock_embed, \
         patch("services.query_router.search_cache") as mock_search, \
         patch("routers.query.save_to_cache") as mock_save, \
         patch("routers.query.generate_recommendation") as mock_rec, \
         patch("routers.query.generate_crawler_script") as mock_script, \
         patch("routers.query.evaluate_lifecycle") as mock_life, \
         patch("routers.query.create_crawler_task") as mock_task:

        mock_embed.return_value = [0.1] * 1536
        mock_search.return_value = None
        mock_save.return_value = "new-cache-uuid"
        mock_rec.return_value = mock_result
        mock_script.return_value = "def run(): return {}"
        mock_life.return_value = mock_lifecycle
        mock_task.return_value = "task-uuid"

        from main import app
        with TestClient(app) as client:
            response = client.post("/api/query", json={"query": "成都吃蹄花"})

        assert response.status_code == 200
        data = response.json()
        assert data["cache_hit"] is False
        assert data["result"]["name"] == "老妈蹄花"
        assert data["result"]["reason"] == "成都最正宗的蹄花汤，老字号"
        assert data["cache_id"] == "new-cache-uuid"

        # Verify the full pipeline was exercised
        mock_embed.assert_called_once_with("成都吃蹄花")
        mock_search.assert_called_once_with([0.1] * 1536)
        mock_rec.assert_called_once_with("成都吃蹄花")
        mock_life.assert_called_once_with("成都吃蹄花")
        mock_save.assert_called_once()
        mock_script.assert_called_once_with("成都吃蹄花", mock_result)
        mock_task.assert_called_once()


def test_full_query_flow_cache_hit():
    """Test the full query flow when there is a cache hit.

    Verifies that a POST to /api/query finds a cached result and
    returns it without calling AI recommendation or crawler creation.
    """
    cached = {
        "id": "cache-uuid",
        "result": {"name": "老妈蹄花", "reason": "成都老字号"},
        "expires_at": "2099-01-01T00:00:00+00:00",
    }

    with patch("main.start_scheduler"), \
         patch("main.shutdown_scheduler"), \
         patch("services.query_router.generate_embedding") as mock_embed, \
         patch("services.query_router.search_cache") as mock_search, \
         patch("services.query_router.update_cache_hit") as mock_update:

        mock_embed.return_value = [0.1] * 1536
        mock_search.return_value = cached

        from main import app
        with TestClient(app) as client:
            response = client.post("/api/query", json={"query": "成都吃蹄花"})

        assert response.status_code == 200
        data = response.json()
        assert data["cache_hit"] is True
        assert data["result"]["name"] == "老妈蹄花"
        assert data["result"]["reason"] == "成都老字号"
        assert data["cache_id"] == "cache-uuid"

        # Verify cache hit path was taken
        mock_embed.assert_called_once_with("成都吃蹄花")
        mock_search.assert_called_once_with([0.1] * 1536)
        mock_update.assert_called_once_with("cache-uuid")
