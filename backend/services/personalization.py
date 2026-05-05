"""Personalization service for tailoring recommendations to individual users."""

BUDGET_MAP = {"低": (0, 50), "中等": (50, 150), "高": (150, 9999)}


def personalize_result(result: dict, preferences: dict) -> dict:
    """Apply personalization rules to a recommendation result.

    Generates a personalization_note based on user preferences
    (budget and cuisine) matching the recommendation content.

    Does NOT mutate the input dict — returns a new dict if a note is added.
    """
    note_parts: list[str] = []

    budget = preferences.get("budget", "中等")
    price_range = result.get("price_range", "")
    if price_range and budget == "低" and "人均" in price_range:
        note_parts.append("价格符合你的预算")

    cuisine_prefs = preferences.get("cuisine", [])
    reason = result.get("reason", "")
    if cuisine_prefs and any(c in reason for c in cuisine_prefs):
        note_parts.append(f"符合你喜欢{'/'.join(cuisine_prefs)}的口味")

    if note_parts:
        return {**result, "personalization_note": "、".join(note_parts)}

    return result
