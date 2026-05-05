import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from main import app

client = TestClient(app)


def test_wx_login_returns_token(mock_wx_response, mock_db):
    with patch("routers.auth.exchange_wx_code") as mock_exchange, \
         patch("routers.auth.get_or_create_user") as mock_user:
        mock_exchange.return_value = "test_openid_123"
        mock_user.return_value = {"id": "user-uuid", "wx_openid": "test_openid_123"}

        response = client.post("/api/auth/wx-login", json={"code": "wx_test_code"})

        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert "user" in data
        assert data["user"]["id"] == "user-uuid"
        assert data["user"]["wx_openid"] == "test_openid_123"
