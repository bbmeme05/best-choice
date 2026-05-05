import pytest
from services.personalization import personalize_result, BUDGET_MAP


class TestPersonalizeResult:
    """Tests for the personalize_result function."""

    def test_returns_original_dict_when_no_preferences_match(self):
        result = {"name": "面馆", "reason": "好吃", "price_range": "人均80"}
        prefs = {"budget": "高", "cuisine": []}
        out = personalize_result(result, prefs)
        assert out == result
        assert "personalization_note" not in out

    def test_does_not_mutate_input_dict(self):
        result = {"name": "面馆", "reason": "川菜好吃", "price_range": "人均30"}
        prefs = {"budget": "低", "cuisine": ["川菜"]}
        original = result.copy()
        out = personalize_result(result, prefs)
        assert result == original  # input not mutated
        assert "personalization_note" in out
        assert out is not result  # new dict returned

    def test_adds_budget_note_for_low_budget(self):
        result = {"name": "面馆", "reason": "好吃", "price_range": "人均30"}
        prefs = {"budget": "低", "cuisine": []}
        out = personalize_result(result, prefs)
        assert out["personalization_note"] == "价格符合你的预算"

    def test_no_budget_note_for_non_low_budget(self):
        result = {"name": "面馆", "reason": "好吃", "price_range": "人均30"}
        prefs = {"budget": "中等", "cuisine": []}
        out = personalize_result(result, prefs)
        assert "personalization_note" not in out

    def test_no_budget_note_when_no_price_range(self):
        result = {"name": "面馆", "reason": "好吃"}
        prefs = {"budget": "低", "cuisine": []}
        out = personalize_result(result, prefs)
        assert "personalization_note" not in out

    def test_no_budget_note_when_price_range_lacks_per_capita(self):
        result = {"name": "面馆", "reason": "好吃", "price_range": "30元"}
        prefs = {"budget": "低", "cuisine": []}
        out = personalize_result(result, prefs)
        assert "personalization_note" not in out

    def test_adds_cuisine_note_when_preference_matches(self):
        result = {"name": "火锅店", "reason": "正宗川菜火锅", "price_range": "人均120"}
        prefs = {"budget": "中等", "cuisine": ["川菜"]}
        out = personalize_result(result, prefs)
        assert out["personalization_note"] == "符合你喜欢川菜的口味"

    def test_no_cuisine_note_when_no_cuisine_preferences(self):
        result = {"name": "火锅店", "reason": "正宗川菜火锅", "price_range": "人均120"}
        prefs = {"budget": "中等", "cuisine": []}
        out = personalize_result(result, prefs)
        assert "personalization_note" not in out

    def test_no_cuisine_note_when_cuisine_not_in_reason(self):
        result = {"name": "面馆", "reason": "地道粤菜", "price_range": "人均120"}
        prefs = {"budget": "中等", "cuisine": ["川菜"]}
        out = personalize_result(result, prefs)
        assert "personalization_note" not in out

    def test_combined_budget_and_cuisine_notes(self):
        result = {"name": "面馆", "reason": "川菜小面", "price_range": "人均30"}
        prefs = {"budget": "低", "cuisine": ["川菜"]}
        out = personalize_result(result, prefs)
        assert out["personalization_note"] == "价格符合你的预算、符合你喜欢川菜的口味"

    def test_multiple_cuisine_preferences(self):
        result = {"name": "餐厅", "reason": "粤菜早茶", "price_range": "人均100"}
        prefs = {"budget": "中等", "cuisine": ["川菜", "粤菜"]}
        out = personalize_result(result, prefs)
        assert "粤菜" in out["personalization_note"]

    def test_empty_preferences_returns_original(self):
        result = {"name": "面馆", "reason": "好吃", "price_range": "人均30"}
        out = personalize_result(result, {})
        assert out == result
        assert "personalization_note" not in out

    def test_default_budget_is_medium(self):
        result = {"name": "面馆", "reason": "好吃", "price_range": "人均30"}
        prefs = {"cuisine": []}  # no budget key, defaults to 中等
        out = personalize_result(result, prefs)
        assert "personalization_note" not in out


class TestBudgetMap:
    """Tests for the BUDGET_MAP constant."""

    def test_budget_map_has_expected_keys(self):
        assert set(BUDGET_MAP.keys()) == {"低", "中等", "高"}

    def test_budget_map_values_are_tuples(self):
        for key, value in BUDGET_MAP.items():
            assert isinstance(value, tuple)
            assert len(value) == 2
            assert value[0] < value[1]
