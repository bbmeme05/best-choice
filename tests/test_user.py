import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from jose import jwt
from config import settings

from main import app

client = TestClient(app)


def _make_token(user_id: str = "user-uuid") -> str:
    """Create a valid JWT token for testing."""
    from datetime import datetime, timedelta, timezone

    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(days=1),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def _make_headers(user_id: str = "user-uuid") -> dict:
    """Create authorization headers with a valid token."""
    return {"Authorization": f"Bearer {_make_token(user_id)}"}


def _mock_user_table(user_data: list[dict]) -> MagicMock:
    """Create a mock table that returns user_data from select().eq().execute()."""
    mock_table = MagicMock()
    mock_result = MagicMock()
    mock_result.data = user_data
    mock_table.select.return_value.eq.return_value.execute.return_value = mock_result
    return mock_table


class TestGetProfile:
    def test_returns_user_profile_with_valid_token(self):
        mock_db = MagicMock()
        mock_db.table.return_value = _mock_user_table(
            [{"id": "user-uuid", "wx_openid": "openid123", "preferences": {}}]
        )

        with patch("routers.user.get_db", return_value=mock_db):
            response = client.get("/api/user/profile", headers=_make_headers())

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "user-uuid"
        assert data["wx_openid"] == "openid123"

    def test_returns_401_without_authorization(self):
        response = client.get("/api/user/profile")
        assert response.status_code == 401
        assert response.json()["detail"] == "未登录"

    def test_returns_401_with_invalid_token(self):
        response = client.get(
            "/api/user/profile", headers={"Authorization": "Bearer invalid-token"}
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Token 无效"

    def test_returns_404_when_user_not_found(self):
        mock_db = MagicMock()
        mock_db.table.return_value = _mock_user_table([])

        with patch("routers.user.get_db", return_value=mock_db):
            response = client.get("/api/user/profile", headers=_make_headers())

        assert response.status_code == 404
        assert response.json()["detail"] == "用户不存在"


class TestUpdatePreferences:
    def test_updates_preferences_with_valid_token(self):
        mock_db = MagicMock()
        mock_table = _mock_user_table(
            [
                {
                    "id": "user-uuid",
                    "preferences": {"cuisine": ["川菜"], "budget": "中等", "city": ""},
                }
            ]
        )
        mock_db.table.return_value = mock_table

        with patch("routers.user.get_db", return_value=mock_db):
            response = client.put(
                "/api/user/preferences",
                json={"budget": "低"},
                headers=_make_headers(),
            )

        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["preferences"]["budget"] == "低"
        assert data["preferences"]["cuisine"] == ["川菜"]  # preserved

    def test_returns_401_without_authorization(self):
        response = client.put(
            "/api/user/preferences", json={"budget": "低"}
        )
        assert response.status_code == 401

    def test_merge_preserves_existing_prefs(self):
        mock_db = MagicMock()
        mock_table = _mock_user_table(
            [
                {
                    "id": "user-uuid",
                    "preferences": {"cuisine": ["川菜"], "budget": "中等", "city": "成都"},
                }
            ]
        )
        mock_db.table.return_value = mock_table

        with patch("routers.user.get_db", return_value=mock_db):
            response = client.put(
                "/api/user/preferences",
                json={"cuisine": ["粤菜", "湘菜"]},
                headers=_make_headers(),
            )

        assert response.status_code == 200
        data = response.json()
        assert data["preferences"]["cuisine"] == ["粤菜", "湘菜"]
        assert data["preferences"]["budget"] == "中等"  # preserved
        assert data["preferences"]["city"] == "成都"  # preserved


class TestGetHistory:
    def test_returns_query_history(self):
        mock_db = MagicMock()
        mock_user_table = _mock_user_table(
            [{"id": "user-uuid", "wx_openid": "openid123"}]
        )
        # History chain: select(...).eq(...).order(...).limit(...).execute()
        mock_history_result = MagicMock()
        mock_history_result.data = [
            {
                "id": "hist-1",
                "user_id": "user-uuid",
                "query_cache": {"result": {"name": "面馆"}, "canonical_query": "吃面"},
            }
        ]
        mock_history_table = MagicMock()
        mock_history_table.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = (
            mock_history_result
        )

        def table_side_effect(name):
            if name == "users":
                return mock_user_table
            return mock_history_table

        mock_db.table.side_effect = table_side_effect

        with patch("routers.user.get_db", return_value=mock_db):
            response = client.get("/api/user/history", headers=_make_headers())

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["query_cache"]["canonical_query"] == "吃面"

    def test_returns_401_without_authorization(self):
        response = client.get("/api/user/history")
        assert response.status_code == 401
