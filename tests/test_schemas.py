"""Validate the contract for both minimal and rich user inputs."""
import json
from pathlib import Path
import pytest
from pydantic import ValidationError
from app.schemas import CourseAdvisorInput


def test_minimal_input():
    request = CourseAdvisorInput.model_validate({"learning_request": {"topic": "UX Design"}})
    assert request.learning_request.level is None
    assert request.preferences.language is None


def test_beginner_sample():
    payload = json.loads((Path(__file__).parent / "sample_input.json").read_text(encoding="utf-8"))
    request = CourseAdvisorInput.model_validate(payload)
    assert request.learning_request.level.value == "beginner"
    assert request.constraints.budget.mode == "free"


def test_missing_topic_is_invalid():
    with pytest.raises(ValidationError):
        CourseAdvisorInput.model_validate({"learning_request": {}})


def test_hard_constraint_requires_value():
    with pytest.raises(ValidationError):
        CourseAdvisorInput.model_validate({
            "learning_request": {"topic": "Data Analysis"},
            "settings": {"hard_constraints": ["language"]}
        })


def test_limited_budget_requires_amount_and_currency():
    with pytest.raises(ValidationError):
        CourseAdvisorInput.model_validate({
            "learning_request": {"topic": "Data Analysis"},
            "constraints": {"budget": {"mode": "limited"}}
        })
