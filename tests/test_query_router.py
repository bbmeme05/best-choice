import pytest
from unittest.mock import patch, MagicMock


def test_cache_hit_returns_result(mock_db):
    cached_result = {
        "id": "cache-uuid",
        "result": {"name": "老字号面馆", "reason": "成都本地人最爱"},
        "expires_at": "2099-01-01T00:00:00+00:00",
    }
    with patch("services.query_router.generate_embedding") as mock_embed, \
         patch("services.query_router.search_cache") as mock_search, \
         patch("services.query_router.update_cache_hit") as mock_update:
        mock_embed.return_value = [0.1] * 1536
        mock_search.return_value = cached_result

        from services.query_router import route_query
        result = route_query("成都吃面", user_id="user-1")

        assert result["cache_hit"] is True
        assert result["result"]["name"] == "老字号面馆"
        assert result["embedding"] == [0.1] * 1536


def test_cache_miss_returns_none(mock_db):
    with patch("services.query_router.generate_embedding") as mock_embed, \
         patch("services.query_router.search_cache") as mock_search:
        mock_embed.return_value = [0.1] * 1536
        mock_search.return_value = None

        from services.query_router import route_query
        result = route_query("火星吃什么", user_id="user-1")

        assert result["cache_hit"] is False
        assert result["result"] is None


def test_cache_hit_updates_hit_count(mock_db):
    cached_result = {
        "id": "cache-uuid",
        "result": {"name": "火锅", "reason": "必吃"},
        "expires_at": "2099-01-01T00:00:00+00:00",
    }
    with patch("services.query_router.generate_embedding") as mock_embed, \
         patch("services.query_router.search_cache") as mock_search, \
         patch("services.query_router.update_cache_hit") as mock_update:
        mock_embed.return_value = [0.1] * 1536
        mock_search.return_value = cached_result

        from services.query_router import route_query
        result = route_query("成都吃火锅", user_id="user-1")

        mock_update.assert_called_once_with("cache-uuid")
        assert result["cache_hit"] is True


def test_cache_miss_does_not_update_hit_count(mock_db):
    with patch("services.query_router.generate_embedding") as mock_embed, \
         patch("services.query_router.search_cache") as mock_search, \
         patch("services.query_router.update_cache_hit") as mock_update:
        mock_embed.return_value = [0.1] * 1536
        mock_search.return_value = None

        from services.query_router import route_query
        result = route_query("火星吃什么", user_id="user-1")

        mock_update.assert_not_called()


def test_generate_embedding_calls_openai():
    mock_response = MagicMock()
    mock_response.data = [MagicMock(embedding=[0.2] * 1536)]

    with patch("services.query_router._openai") as mock_client:
        mock_client.embeddings.create.return_value = mock_response

        from services.query_router import generate_embedding
        embedding = generate_embedding("成都吃面")

        mock_client.embeddings.create.assert_called_once_with(
            model="text-embedding-ada-002",
            input="成都吃面",
        )
        assert embedding == [0.2] * 1536


def test_search_cache_returns_cached_row():
    embedding = [0.1] * 1536
    mock_db_client = MagicMock()
    mock_result = MagicMock()
    mock_result.data = [{
        "id": "cache-uuid",
        "result": {"name": "面馆"},
        "expires_at": "2099-01-01T00:00:00+00:00",
    }]
    mock_db_client.rpc.return_value.execute.return_value = mock_result

    with patch("services.query_router.get_db", return_value=mock_db_client):
        from services.query_router import search_cache
        result = search_cache(embedding)

    assert result is not None
    assert result["id"] == "cache-uuid"
    assert result["result"]["name"] == "面馆"


def test_search_cache_returns_none_when_empty():
    embedding = [0.1] * 1536
    mock_db_client = MagicMock()
    mock_result = MagicMock()
    mock_result.data = []
    mock_db_client.rpc.return_value.execute.return_value = mock_result

    with patch("services.query_router.get_db", return_value=mock_db_client):
        from services.query_router import search_cache
        result = search_cache(embedding)

    assert result is None


def test_search_cache_returns_none_when_expired():
    embedding = [0.1] * 1536
    mock_db_client = MagicMock()
    mock_result = MagicMock()
    mock_result.data = [{
        "id": "cache-uuid",
        "result": {"name": "面馆"},
        "expires_at": "2000-01-01T00:00:00+00:00",
    }]
    mock_db_client.rpc.return_value.execute.return_value = mock_result

    with patch("services.query_router.get_db", return_value=mock_db_client):
        from services.query_router import search_cache
        result = search_cache(embedding)

    assert result is None


def test_update_cache_hit_increments_count():
    mock_db_client = MagicMock()
    mock_table = MagicMock()
    mock_db_client.table.return_value = mock_table

    mock_select_result = MagicMock()
    mock_select_result.data = {"hit_count": 5}
    mock_table.select.return_value.eq.return_value.single.return_value.execute.return_value = mock_select_result

    with patch("services.query_router.get_db", return_value=mock_db_client):
        from services.query_router import update_cache_hit
        update_cache_hit("cache-uuid")

    # Verify select was called to get current count
    mock_table.select.assert_called_once_with("hit_count")
    mock_table.select.return_value.eq.assert_called_once_with("id", "cache-uuid")

    # Verify update was called with incremented count
    mock_table.update.assert_called_once()
    update_call_args = mock_table.update.call_args[0][0]
    assert update_call_args["hit_count"] == 6
