import json

from openai import OpenAI

from config import settings

_kimi_client = OpenAI(
    api_key=settings.kimi_api_key,
    base_url="https://api.moonshot.cn/v1",
)


def generate_recommendation(query: str) -> dict:
    """Use Kimi web search to find the best recommendation for a query."""
    response = _kimi_client.chat.completions.create(
        model="moonshot-v1-8k",
        messages=[
            {
                "role": "system",
                "content": (
                    "你是一个帮助用户做选择的 AI。根据用户的问题，通过联网搜索找到当前最优推荐。"
                    "只推荐一个，不要给列表。以 JSON 格式返回，包含字段：name, reason, address, price_range, rating, link。"
                    "如果某字段无法获取，设为 null。只返回 JSON，不要有其他文字。"
                ),
            },
            {"role": "user", "content": query},
        ],
        tools=[{"type": "builtin_function", "function": {"name": "$web_search"}}],
        temperature=0.3,
    )
    content = response.choices[0].message.content
    return json.loads(content)


def generate_crawler_script(query: str, result: dict) -> str:
    """Generate a Python crawler script that keeps the recommendation data fresh."""
    prompt = f"""
用户问题：{query}
当前推荐结果：{json.dumps(result, ensure_ascii=False)}

请生成一个 Python 爬虫脚本，定期获取与这个推荐相关的最新数据。
要求：
1. 使用 requests 或 httpx 库
2. 脚本返回一个 dict，格式与上面的推荐结果相同
3. 入口函数名为 run()，无参数，返回推荐结果 dict
4. 只返回 Python 代码，不要有说明文字
"""
    response = _kimi_client.chat.completions.create(
        model="moonshot-v1-8k",
        messages=[
            {
                "role": "system",
                "content": "你是一个 Python 爬虫专家，只输出可执行的 Python 代码。",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )
    code = response.choices[0].message.content
    # Strip markdown code fences if present
    if code.startswith("```python"):
        code = code[9:]
    if code.startswith("```"):
        code = code[3:]
    if code.endswith("```"):
        code = code[:-3]
    return code.strip()


def evaluate_lifecycle(query: str) -> dict:
    """Evaluate the data lifecycle type and refresh schedule for a query."""
    prompt = f"""
问题：{query}

评估这个推荐问题的数据生命周期。返回 JSON，包含：
- lifecycle_type: "evergreen"（永久有效，如城市美食）/ "seasonal"（季节性，如防晒霜夏季）/ "ephemeral"（短期，如活动推荐）
- schedule_interval: 爬虫更新频率，如 "7d"、"30d"、"1d"
- ttl_days: 整个任务的存活天数（int）

只返回 JSON。
"""
    response = _kimi_client.chat.completions.create(
        model="moonshot-v1-8k",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
    )
    return json.loads(response.choices[0].message.content)
