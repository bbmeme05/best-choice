import os
import sys
from pathlib import Path

import pytest
from unittest.mock import MagicMock, patch

# Set test environment variables before any backend module is imported
_test_env = {
    "SUPABASE_URL": "https://test.supabase.co",
    "SUPABASE_KEY": "test-key",
    "KIMI_API_KEY": "test-kimi-key",
    "OPENAI_API_KEY": "test-openai-key",
    "WX_APP_ID": "test-wx-appid",
    "WX_APP_SECRET": "test-wx-secret",
    "JWT_SECRET": "test-jwt-secret",
}
for key, value in _test_env.items():
    os.environ.setdefault(key, value)

# Add backend/ to sys.path so tests can import backend modules
backend_dir = Path(__file__).resolve().parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))


@pytest.fixture
def mock_db():
    with patch("database.get_db") as mock:
        mock_client = MagicMock()
        mock.return_value = mock_client
        yield mock_client


@pytest.fixture
def mock_wx_response():
    return {"openid": "test_openid_123", "session_key": "test_session_key"}
