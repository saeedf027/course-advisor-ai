"""Contract tests for Agent output, without calling a paid LLM."""
import json
from pathlib import Path
import pytest
from pydantic import ValidationError
from app.schemas import CourseAdvisorInput
from Agent.needs_schema import LearningNeedsProfile, verify_profile_against_input


def example_profile():
    return {
        "topic": "تحلیل داده",
        "resolved_level": "beginner",
        "level_source": "explicit",
        "level_confidence": "high",
        "learning_intent": "یادگیری مقدماتی تحلیل داده‌های کسب‌وکار",
        "search_topics": ["مبانی تحلیل داده", "تحلیل داده با اکسل", "مصورسازی داده"],
        "suggested_prerequisites": ["مفاهیم اولیه صفحه گسترده"],
        "hard_constraints": ["budget"],
        "needs_learning_path": True,
        "notes": []
    }


def sample_request():
    payload = json.loads((Path(__file__).parent / "sample_input.json").read_text(encoding="utf-8"))
    return CourseAdvisorInput.model_validate(payload)


def test_beginner_profile_matches_request():
    request = sample_request()
    profile = LearningNeedsProfile.model_validate(example_profile())
    verify_profile_against_input(profile, request)


def test_reject_hard_constraint_mutation():
    request = sample_request()
    payload = example_profile()
    payload["hard_constraints"] = []
    profile = LearningNeedsProfile.model_validate(payload)
    with pytest.raises(ValueError):
        verify_profile_against_input(profile, request)


def test_reject_fake_explicit_level():
    request = CourseAdvisorInput.model_validate({"learning_request": {"topic": "تحلیل داده"}})
    profile = LearningNeedsProfile.model_validate(example_profile() | {"hard_constraints": []})
    with pytest.raises(ValueError):
        verify_profile_against_input(profile, request)


def test_unknown_level_requires_no_beginner_path():
    payload = example_profile() | {
        "resolved_level": "unknown",
        "level_source": "unknown",
        "level_confidence": "low",
        "hard_constraints": [],
        "needs_learning_path": False,
    }
    assert LearningNeedsProfile.model_validate(payload).needs_learning_path is False


def test_inconsistent_learning_path_is_rejected():
    payload = example_profile() | {"needs_learning_path": False}
    with pytest.raises(ValidationError):
        LearningNeedsProfile.model_validate(payload)
