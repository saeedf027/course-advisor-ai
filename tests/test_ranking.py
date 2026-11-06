"""Offline tests of step 05; all course records are mock data."""
import pytest

from Agent.needs_schema import LearningNeedsProfile
from app.schemas import CourseAdvisorInput
from Tools.rank import FitAssessment, check_eligibility, rank_courses
from Tools.validate import CourseDraft, CourseReview


def inputs(hard=None):
    hard = hard or []
    request = CourseAdvisorInput.model_validate({
        "learning_request": {"topic": "تحلیل داده", "level": "beginner"},
        "constraints": {"budget": {"mode": "free"}},
        "settings": {"hard_constraints": hard},
    })
    profile = LearningNeedsProfile.model_validate({
        "topic": "تحلیل داده", "resolved_level": "beginner",
        "level_source": "explicit", "level_confidence": "high",
        "learning_intent": "یادگیری تحلیل داده",
        "search_topics": ["تحلیل داده", "مصورسازی", "اکسل"],
        "hard_constraints": hard, "needs_learning_path": True
    })
    return request, profile


def course(i, provider=None, price="free", status="verified"):
    draft = CourseDraft(
        name=f"Course {i}", provider=provider or f"Institute {i}",
        level="Beginner", audience="Beginners", topics=["data"],
        price=price, source_url=f"https://example.org/course/{i}"
    )
    return CourseReview(status=status, record=draft)


def assessment(i, score=5):
    return FitAssessment(
        course_url=f"https://example.org/course/{i}",
        topic=score, level=score, intent=score, pedagogy=score,
        reason_fa="این دوره موضوع موردنظر را برای یادگیرنده مبتدی پوشش می‌دهد."
    )


def test_six_distinct_providers_ready():
    request, profile = inputs(["budget"])
    result = rank_courses([course(i) for i in range(6)],
                          [assessment(i) for i in range(6)], request, profile)
    assert result.status == "ready"
    assert len(result.selected) == 6
    assert all(c.match_score == 100 for c in result.selected)


def test_unknown_price_fails_closed():
    request, _ = inputs(["budget"])
    assert check_eligibility(course(1, price=None), request) == [
        "hard_constraint_unverified_or_mismatch:budget"
    ]


def test_high_score_does_not_override_paid_course():
    request, profile = inputs(["budget"])
    reviews = [course(0, price="paid")] + [course(i) for i in range(1, 7)]
    assessments = [assessment(0, 5)] + [assessment(i, 4) for i in range(1, 7)]
    result = rank_courses(reviews, assessments, request, profile)
    assert result.status == "ready"
    assert all(x.course.name != "Course 0" for x in result.selected)


def test_insufficient_sources_is_not_a_completed_report():
    request, profile = inputs([])
    result = rank_courses([course(i) for i in range(3)],
                          [assessment(i) for i in range(3)], request, profile)
    assert result.status == "insufficient_verified_courses"
    assert result.selected == []


def test_duplicate_provider_never_fills_six():
    request, profile = inputs([])
    reviews = [course(i, provider="Same Institute") for i in range(7)]
    result = rank_courses(reviews, [assessment(i) for i in range(7)], request, profile)
    assert result.status == "insufficient_verified_courses"


def test_unverified_review_excluded():
    request, profile = inputs([])
    reviews = [course(0, status="incomplete")] + [course(i) for i in range(1, 7)]
    result = rank_courses(reviews, [assessment(i) for i in range(7)], request, profile)
    assert result.status == "ready"
    assert all(item.course.name != "Course 0" for item in result.selected)


def test_score_weights():
    request, profile = inputs([])
    items = [course(i) for i in range(6)]
    assess = [assessment(i, 5) for i in range(6)]
    assess[0] = FitAssessment(
        course_url="https://example.org/course/0", topic=5, level=0,
        intent=5, pedagogy=0,
        reason_fa="موضوع مرتبط است اما سطح و شیوه تدریس کمتر تناسب دارند."
    )
    result = rank_courses(items, assess, request, profile)
    item = next(x for x in result.selected if x.course.name == "Course 0")
    assert item.match_score == 60


def test_missing_assessment_does_not_fabricate_score():
    request, profile = inputs([])
    result = rank_courses([course(i) for i in range(6)],
                          [assessment(i) for i in range(5)], request, profile)
    assert result.status == "insufficient_verified_courses"


def test_free_is_soft_preference_when_not_explicitly_hard():
    request, profile = inputs([])
    assert check_eligibility(course(0, price="paid"), request) == []
    reviews = [course(0, price="paid")] + [course(i) for i in range(1, 6)]
    result = rank_courses(
        reviews, [assessment(i) for i in range(6)], request, profile
    )
    assert result.status == "ready"
    by_name = {item.course.name: item for item in result.selected}
    assert by_name["Course 0"].match_score == 93
    assert "رایگان" in by_name["Course 0"].limitations_fa
    assert by_name["Course 1"].match_score == 100


def test_unknown_price_is_penalty_not_exclusion_for_soft_budget():
    request, profile = inputs([])
    assert check_eligibility(course(0, price=None), request) == []
    reviews = [course(0, price=None)] + [course(i) for i in range(1, 6)]
    result = rank_courses(
        reviews, [assessment(i) for i in range(6)], request, profile
    )
    assert result.status == "ready"
    result_zero = next(x for x in result.selected if x.course.name == "Course 0")
    assert result_zero.match_score == 97
    assert "رایگان" in result_zero.limitations_fa


def test_hard_budget_still_blocks_paid_or_unknown_courses():
    request, _ = inputs(["budget"])
    assert check_eligibility(course(0, price="paid"), request)
    assert check_eligibility(course(0, price=None), request)


def test_soft_language_and_format_reduce_score_without_exclusion():
    request, profile = inputs([])
    request.preferences.language = "fa"
    request.preferences.format = "recorded_online"
    reviews = [course(i) for i in range(6)]
    reviews[0].record.language = "English"
    reviews[0].record.format = "live_online"
    result = rank_courses(reviews, [assessment(i) for i in range(6)], request, profile)
    mismatch = next(x for x in result.selected if x.course.name == "Course 0")
    assert mismatch.match_score == 92
    assert "زبان" in mismatch.limitations_fa
    assert "شیوه" in mismatch.limitations_fa
