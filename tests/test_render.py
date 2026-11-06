"""Step 07 renderer tests — use synthetic examples, no external APIs."""
from pathlib import Path
import pytest

from app.schemas import CourseAdvisorInput
from Agent.needs_schema import LearningNeedsProfile
from Tools.rank import RankedCourse, RankingResult
from Tools.validate import CourseDraft
from Tools.roadmap import LearningRoadmap
from Tools.render import render_report, save_report


def fixture(beginner=True, ready=True):
    level = "beginner" if beginner else "intermediate"
    req = CourseAdvisorInput.model_validate({
        "learning_request": {"topic": "<script>alert(1)</script> تحلیل داده", "level": level},
        "preferences": {"language": "fa"},
    })
    profile = LearningNeedsProfile.model_validate({
        "topic": req.learning_request.topic, "resolved_level": level,
        "level_source": "explicit", "level_confidence": "high",
        "learning_intent": "یادگیری داده", "search_topics": ["داده", "اکسل", "نمودار"],
        "needs_learning_path": beginner,
    })
    cards = [
        RankedCourse(
            course=CourseDraft(
                name=f"دوره آموزشی {i}", provider=f"مؤسسه نمونه {i}",
                audience="افراد تازه‌کار", topics=["مبانی", "کاربرد"],
                level="مبتدی", source_url=f"https://example.org/course/{i}"
            ),
            match_score=90-i, reason_fa="تناسب آموزشی با نیاز مطرح شده",
            score_breakdown={"topic": 30},
        ) for i in range(6)
    ]
    result = RankingResult(
        status="ready" if ready else "insufficient_verified_courses",
        selected=cards if ready else [], eligible_count=6, excluded_count=0,
        warnings=["تعداد نتایج قابل تأیید کافی نبود."] if not ready else [],
    )
    path = None
    if beginner and ready:
        path = LearningRoadmap.model_validate({
            "title": "مسیر یادگیری تحلیل داده", "summary": "مسیر تدریجی آموزش و تمرین تحلیل داده برای مبتدیان",
            "audience_level": "beginner",
            "duration_disclaimer": "برآورد زمان تقریبی است و به میزان تمرین فرد بستگی دارد.",
            "steps": [{
                "step_number": i+1, "title": f"گام آموزشی {i+1}",
                "goal": "توسعه دانش و مهارت‌های مرتبط با نیاز آموزشی کاربر",
                "skills": ["تمرین", "مبانی"],
                "recommended_course_urls": [
                    f"https://example.org/course/{2*i}", f"https://example.org/course/{2*i+1}"
                ],
            } for i in range(3)]
        })
    return req, profile, result, path


def test_beginner_has_six_cards_and_visual_timeline():
    html = render_report(*fixture(), demo=True)
    assert html.count('class="course"') == 6
    assert html.count('class="step"') == 3
    assert "مسیر یادگیری تحلیل داده" in html
    assert "فقط داده نمایشی" in html
    assert "dir=\"rtl\"" in html


def test_non_beginner_omits_timeline():
    html = render_report(*fixture(beginner=False), demo=True)
    assert html.count('class="course"') == 6
    assert 'id="roadmap"' not in html


def test_insufficient_renders_no_courses_or_roadmap():
    html = render_report(*fixture(ready=False), demo=True)
    assert 'class="course"' not in html
    assert 'id="roadmap"' not in html
    assert "نتیجه ناکافی است" in html


def test_escaping_prevents_script_injection():
    html = render_report(*fixture(), demo=True)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_reject_unsafe_course_link():
    req, prof, ranking, roadmap = fixture(beginner=False)
    ranking.selected[0].course.source_url = "javascript:alert(1)"
    with pytest.raises(ValueError):
        render_report(req, prof, ranking, roadmap)


def test_saved_html_has_utf8_encoding(tmp_path):
    path = save_report(render_report(*fixture(), demo=True), tmp_path / "report.html")
    assert path.read_text(encoding="utf-8").startswith("<!doctype html>")
    assert path.suffix == ".html"

def test_partial_preview_has_scores_but_no_completed_six_or_roadmap():
    req, prof, complete, _ = fixture()
    partial = RankingResult(
        status="insufficient_verified_courses", selected=[],
        preview=complete.selected[:3], eligible_count=3, excluded_count=0,
        warnings=["Only three source-backed courses found."],
    )
    html = render_report(req, prof, partial, None, demo=True)
    assert html.count('class="course"') == 3
    assert "پیشنهادهای اولیه" in html
    assert "نتیجه ناکافی است" in html
    assert "شش دوره پیشنهادی" not in html
    assert 'id="roadmap"' not in html
    assert "٪ تناسب پیشنهادی" in html
