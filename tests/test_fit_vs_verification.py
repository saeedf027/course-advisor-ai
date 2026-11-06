"""Offline checks: course identity verification is distinct from graded fit."""
from Tools.validate import CourseDraft, Evidence, review_course
from Tools.rank import FitAssessment, rank_courses
from app.schemas import CourseAdvisorInput
from Agent.needs_schema import LearningNeedsProfile


def evidence(url, field, quote):
    return Evidence(field=field, source_url=url, quote=quote)


def test_source_backed_course_accepted_without_audience_and_duration():
    url = "https://courses.example.org/data-analysis"
    page = "دوره تحلیل داده مقدماتی\nمرکز آموزش نمونه\nسرفصل: اکسل و نمودار"
    draft = CourseDraft(
        name="دوره تحلیل داده مقدماتی", provider="مرکز آموزش نمونه",
        topics=["اکسل و نمودار"], source_url=url,
        evidence=[
            evidence(url, "name", "دوره تحلیل داده مقدماتی"),
            evidence(url, "provider", "مرکز آموزش نمونه"),
            evidence(url, "topics", "اکسل و نمودار"),
        ],
    )
    reviewed = review_course(draft, page, url)
    assert reviewed.status == "verified"
    assert reviewed.record.audience is None
    assert reviewed.record.duration is None
    assert "audience" in reviewed.missing_fields


def test_unsupported_price_is_removed_not_assumed_free():
    url = "https://courses.example.org/data"
    draft = CourseDraft(
        name="Data Skills", provider="Example Academy",
        level="Beginner", price="free", source_url=url,
        evidence=[
            evidence(url, "name", "Data Skills"),
            evidence(url, "provider", "Example Academy"),
            evidence(url, "level", "Beginner"),
        ],
    )
    review = review_course(draft, "Data Skills - Example Academy - Beginner", url)
    assert review.status == "verified"
    assert review.record.price is None
    from Tools.rank import check_eligibility
    req = CourseAdvisorInput.model_validate({
        "learning_request": {"topic": "Data Skills"},
        "constraints": {"budget": {"mode": "free"}},
        "settings": {"hard_constraints": ["budget"]},
    })
    assert check_eligibility(review, req) == [
        "hard_constraint_unverified_or_mismatch:budget"
    ]


def test_course_identity_without_evidence_is_not_verified():
    url = "https://courses.example.org/data"
    draft = CourseDraft(name="Imagined Course", provider="Imagined Academy",
                        topics=["Python"], source_url=url)
    result = review_course(draft, "A generic page about courses", url)
    assert result.status == "incomplete"


def test_mismatched_optional_claim_is_dropped():
    url = "https://courses.example.org/data"
    draft = CourseDraft(
        name="Data Skills", provider="Example Academy", level="Beginner",
        audience="Senior experts", source_url=url,
        evidence=[
            evidence(url, "name", "Data Skills"),
            evidence(url, "provider", "Example Academy"),
            evidence(url, "level", "Beginner"),
            evidence(url, "audience", "Senior experts"),
        ],
    )
    review = review_course(draft, "Data Skills Example Academy Beginner", url)
    assert review.status == "verified"
    assert review.record.audience is None


def test_eighty_percent_fit_and_known_limitations():
    from Tools.rank import _score
    a = FitAssessment(
        course_url="https://example.org/course",
        topic=5, level=4, intent=4, pedagogy=3,
        reason_fa="این دوره مبانی موردنیاز را پوشش می‌دهد و برای شروع مناسب است.",
        limitations_fa="بخش تمرین عملی آن محدودتر از ترجیح کاربر است.",
    )
    score, parts = _score(a)
    assert score == 84
    assert a.limitations_fa is not None
