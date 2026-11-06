"""Step 07: render validated recommendation data into a safe Persian RTL HTML report.

This is a formatter, NOT a source verifier or a generator of course facts.
"""
from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.schemas import CourseAdvisorInput
from Agent.needs_schema import LearningNeedsProfile, verify_profile_against_input
from Tools.rank import RankingResult
from Tools.roadmap import LearningRoadmap, validate_roadmap
from Tools.search import canonical_url

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "app" / "templates"
ENV = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
    trim_blocks=True,
    lstrip_blocks=True,
)

LEVEL_LABELS = {
    "beginner": "مبتدی", "intermediate": "متوسط",
    "advanced": "پیشرفته", "unknown": "مشخص نشده",
}
FORMAT_LABELS = {
    "in_person": "حضوری", "live_online": "آنلاین زنده",
    "recorded_online": "آنلاین ضبط‌شده", "hybrid": "ترکیبی",
}
STYLE_LABELS = {"practical": "عملی", "theoretical": "نظری", "mixed": "ترکیبی"}
CERT_LABELS = {
    "required": "ضروری", "preferred": "ترجیحی",
    "not_important": "اهمیتی ندارد",
}
BUDGET_LABELS = {"free": "رایگان", "limited": "بودجه محدود", "unrestricted": "بدون محدودیت"}
DURATION_LABELS = {"short": "کوتاه‌مدت", "medium": "میان‌مدت", "long": "بلندمدت"}


def _source_url(value: str) -> str:
    """Only allow public HTTPS course URLs in a rendered recommendation."""
    normalized = canonical_url(value)
    if normalized is None or not normalized.startswith("https://"):
        raise ValueError("Only HTTPS source links can be shown in final reports.")
    return normalized


def _input_summary(request: CourseAdvisorInput, profile: LearningNeedsProfile) -> list[dict[str, str]]:
    b = request.constraints.budget
    budget = BUDGET_LABELS.get(b.mode) if b.mode else None
    if b.mode == "limited":
        budget = f"تا {b.max_amount:g} {b.currency}"
    values = [
        ("موضوع", request.learning_request.topic),
        ("توضیحات کاربر", request.learning_request.description),
        ("سطح", LEVEL_LABELS[profile.resolved_level]),
        ("زبان ترجیحی", request.preferences.language),
        ("شیوه برگزاری", FORMAT_LABELS.get(request.preferences.format)),
        ("سبک یادگیری", STYLE_LABELS.get(request.preferences.learning_style)),
        ("گواهینامه", CERT_LABELS.get(request.preferences.certificate)),
        ("بودجه", budget),
        ("موقعیت", request.constraints.location),
        ("زمان هفتگی", f"{request.constraints.weekly_hours:g} ساعت" if request.constraints.weekly_hours else None),
        ("مدت موردنظر", DURATION_LABELS.get(request.constraints.duration)),
        ("محدودیت‌های قطعی", "، ".join(request.settings.hard_constraints) if request.settings.hard_constraints else None),
    ]
    return [{"label": label, "value": str(value)} for label, value in values if value is not None]


def render_report(request: CourseAdvisorInput, profile: LearningNeedsProfile,
                  ranking: RankingResult,
                  roadmap: LearningRoadmap | None = None,
                  *, demo: bool = False) -> str:
    """Return a standalone HTML string.

    A completed report requires six selected courses. An insufficient-results
    report clearly communicates failure, without making up any courses.
    The demo flag is only for explicitly synthetic fixtures; never use it to
    label fabricated records as live recommendations.
    """
    verify_profile_against_input(profile, request)
    validate_roadmap(roadmap, request, profile, ranking)
    if ranking.status == "ready" and len(ranking.selected) != 6:
        raise ValueError("Ready report must contain exactly six courses.")
    if ranking.status != "ready" and ranking.selected:
        raise ValueError("Insufficient results must not be shown as final recommendations.")
    cards = []
    if ranking.status == "ready":
        seen_urls: set[str] = set()
        seen_providers: set[str] = set()
        for ranked in ranking.selected:
            course = ranked.course
            url = _source_url(course.source_url)
            provider = (course.provider or "").strip()
            if not course.name or not provider:
                raise ValueError("Missing required course identity.")
            provider_key = " ".join(provider.casefold().split())
            if url in seen_urls or provider_key in seen_providers:
                raise ValueError("Duplicate URL or provider in final report.")
            seen_urls.add(url)
            seen_providers.add(provider_key)
            cards.append({
                "name": course.name, "provider": provider, "level": course.level,
                "duration": course.duration, "audience": course.audience,
                "topics": course.topics, "language": course.language,
                "format": course.format, "price": course.price,
                "reason": ranked.reason_fa, "score": ranked.match_score, "url": url,
                "limitations": ranked.limitations_fa,
                "unknown_fields": ranked.unknown_fields,
            })
    steps = []
    if roadmap is not None:
        indexed_courses = {c["url"]: c for c in cards}
        for stage in roadmap.steps:
            steps.append({
                "number": stage.step_number, "title": stage.title,
                "goal": stage.goal, "skills": stage.skills,
                "prerequisites": stage.prerequisites,
                "duration": (
                    f"{stage.estimated_weeks_min} تا {stage.estimated_weeks_max} هفته"
                    if stage.estimated_weeks_min is not None else None
                ),
                "time_note": stage.estimated_time_note,
                "courses": [indexed_courses[_source_url(u)] for u in stage.recommended_course_urls],
            })
    template = ENV.get_template("report.html")
    return template.render(
        topic=request.learning_request.topic,
        summary=_input_summary(request, profile), cards=cards,
        steps=steps, roadmap=roadmap, ready=ranking.status == "ready",
        warnings=ranking.warnings, demo=demo,
    )


def save_report(html: str, destination: str | Path) -> Path:
    """Save a report as UTF-8 HTML; intended destination is outputs/."""
    path = Path(destination)
    if path.suffix.lower() != ".html":
        raise ValueError("Report destination must end with .html")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    return path
