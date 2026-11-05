"""Step 06 contract tests; fake courses only, no API keys required."""
import pytest
from pydantic import ValidationError

from app.schemas import CourseAdvisorInput
from Agent.needs_schema import LearningNeedsProfile
from Tools.rank import RankingResult, RankedCourse
from Tools.validate import CourseDraft
from Tools.roadmap import LearningRoadmap, validate_roadmap


def fixtures(level="beginner", ready=True):
    request = CourseAdvisorInput.model_validate({
        "learning_request": {"topic": "تحلیل داده", "level": level}
    })
    profile = LearningNeedsProfile.model_validate({
        "topic": "تحلیل داده", "resolved_level": level, "level_source": "explicit",
        "level_confidence": "high", "learning_intent": "شروع تحلیل داده",
        "search_topics": ["داده", "اکسل", "نمودار"],
        "needs_learning_path": level == "beginner",
    })
    selected = [
        RankedCourse(course=CourseDraft(
            name=f"Course {i}", provider=f"Provider {i}", audience="Beginners",
            level="Beginner", topics=["Data"], source_url=f"https://example.org/course/{i}"
        ), match_score=80, reason_fa="متناسب با شروع یادگیری تحلیل داده",
        score_breakdown={"topic": 28})
        for i in range(6)
    ]
    ranking = RankingResult(status="ready" if ready else "insufficient_verified_courses",
                            selected=selected if ready else [], eligible_count=6,
                            excluded_count=0)
    return request, profile, ranking


def roadmap_payload():
    return {
        "title": "مسیر یادگیری تحلیل داده برای مبتدیان",
        "summary": "این مسیر از مفاهیم پایه شروع شده و به تمرین پروژه واقعی می‌رسد.",
        "audience_level": "beginner",
        "duration_disclaimer": "مدت‌ها تخمینی‌اند و با سرعت یادگیری فرد متفاوت خواهند بود.",
        "steps": [
            {
                "step_number": i + 1,
                "title": f"مرحله یادگیری {i + 1}",
                "goal": f"در این مرحله مهارت‌های پایه بخش {i + 1} آموزش داده می‌شوند.",
                "skills": ["تمرین عملی", "مبانی موضوع"],
                "prerequisites": [] if i == 0 else ["مرحله پیشین"],
                "recommended_course_urls": [
                    f"https://example.org/course/{2*i}",
                    f"https://example.org/course/{2*i+1}",
                ],
                "estimated_weeks_min": 1,
                "estimated_weeks_max": 2,
                "estimated_time_note": "تخمین آموزشی، نه زمان قطعی دوره",
            }
            for i in range(3)
        ],
    }


def test_valid_roadmap_covers_all_six():
    request, profile, ranking = fixtures()
    roadmap = LearningRoadmap.model_validate(roadmap_payload())
    validate_roadmap(roadmap, request, profile, ranking)


def test_non_beginner_has_no_roadmap():
    request, profile, ranking = fixtures(level="intermediate")
    validate_roadmap(None, request, profile, ranking)
    with pytest.raises(ValueError):
        validate_roadmap(LearningRoadmap.model_validate(roadmap_payload()),
                         request, profile, ranking)


def test_not_ready_has_no_roadmap():
    request, profile, ranking = fixtures(ready=False)
    validate_roadmap(None, request, profile, ranking)
    with pytest.raises(ValueError):
        validate_roadmap(LearningRoadmap.model_validate(roadmap_payload()),
                         request, profile, ranking)


def test_missing_selected_course_rejected():
    request, profile, ranking = fixtures()
    payload = roadmap_payload()
    payload["steps"][-1]["recommended_course_urls"].pop()
    with pytest.raises(ValueError, match="Every selected course"):
        validate_roadmap(LearningRoadmap.model_validate(payload), request, profile, ranking)


def test_unselected_url_rejected():
    request, profile, ranking = fixtures()
    payload = roadmap_payload()
    payload["steps"][0]["recommended_course_urls"][0] = "https://unrelated.example.org/new"
    with pytest.raises(ValueError, match="unselected course"):
        validate_roadmap(LearningRoadmap.model_validate(payload), request, profile, ranking)


def test_out_of_order_stages_rejected():
    payload = roadmap_payload()
    payload["steps"][1]["step_number"] = 4
    with pytest.raises(ValidationError):
        LearningRoadmap.model_validate(payload)


def test_invalid_duration_range_rejected():
    payload = roadmap_payload()
    payload["steps"][0]["estimated_weeks_min"] = 4
    payload["steps"][0]["estimated_weeks_max"] = 2
    with pytest.raises(ValidationError):
        LearningRoadmap.model_validate(payload)


def test_duplicate_course_reference_in_step_rejected():
    payload = roadmap_payload()
    payload["steps"][0]["recommended_course_urls"] *= 2
    with pytest.raises(ValidationError):
        LearningRoadmap.model_validate(payload)
