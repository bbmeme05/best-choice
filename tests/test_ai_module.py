from unittest.mock import patch, MagicMock


def test_generate_recommendation_returns_structured_result():
    mock_response = MagicMock()
    mock_response.choices[0].message.content = '''{
        "name": "蜀九香火锅",
        "reason": "成都本地老牌火锅，食材新鲜，价格实惠",
        "address": "成都市锦江区XX路",
        "price_range": "人均80-120元",
        "rating": 4.8,
        "link": "https://example.com"
    }'''

    with patch("services.ai_module._kimi_client.chat.completions.create") as mock_create:
        mock_create.return_value = mock_response

        from services.ai_module import generate_recommendation
        result = generate_recommendation("成都吃火锅")

        assert result["name"] == "蜀九香火锅"
        assert result["reason"] is not None
        assert "price_range" in result


def test_generate_crawler_script_returns_python_code():
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "import requests\n# crawler code"

    with patch("services.ai_module._kimi_client.chat.completions.create") as mock_create:
        mock_create.return_value = mock_response

        from services.ai_module import generate_crawler_script
        script = generate_crawler_script("成都吃火锅", {"name": "蜀九香"})

        assert "import" in script


def test_generate_crawler_script_strips_markdown_fences():
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "```python\nimport requests\ndef run(): pass\n```"

    with patch("services.ai_module._kimi_client.chat.completions.create") as mock_create:
        mock_create.return_value = mock_response

        from services.ai_module import generate_crawler_script
        script = generate_crawler_script("测试", {"name": "test"})

        assert not script.startswith("```")
        assert not script.endswith("```")
        assert "import requests" in script


def test_evaluate_lifecycle_returns_valid_type():
    mock_response = MagicMock()
    mock_response.choices[0].message.content = '{"lifecycle_type": "evergreen", "schedule_interval": "7d", "ttl_days": 365}'

    with patch("services.ai_module._kimi_client.chat.completions.create") as mock_create:
        mock_create.return_value = mock_response

        from services.ai_module import evaluate_lifecycle
        result = evaluate_lifecycle("成都吃火锅")

        assert result["lifecycle_type"] in ("evergreen", "seasonal", "ephemeral")
        assert result["schedule_interval"].endswith("d")
