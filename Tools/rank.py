"""Step 05 — deterministic course filtering, scoring and selection.

LLM relevance judgments are supplied as bounded, auditable assessments.
Only source-evidenced course records that passed Step 04 enter this module.
"""
from __future__ import annotations

import re
from typing import Literal

from pydantic import Field

from Agent.needs_schema import LearningNeedsProfile, verify_profile_against_input
from app.schemas import CourseAdvisorInput, StrictModel
from Tools.search import canonical_url
from Tools.validate import CourseReview, CourseDraft, course_identity

WEIGHTS = {"topic": 35, "level": 25, "intent": 25, "pedagogy": 15}


class FitAssessment(StrictModel):
    """Human/LLM judgments on a 0–5 scale; not a verified external rating."""
    course_url: str
    topic: int = Field(ge=0, le=5)
    level: int = Field(ge=0, le=5)
    intent: int = Field(ge=0, le=5)
    pedagogy: int = Field(ge=0, le=5)
    reason_fa: str = Field(min_length=10, max_length=600)
    limitations_fa: str | None = Field(default=None, max_length=400)


class RankedCourse(StrictModel):
    course: CourseDraft
    match_score: int = Field(ge=0, le=100)
    reason_fa: str
    score_breakdown: dict[str, int]
    limitations_fa: str | None = None
    unknown_fields: list[str] = Field(default_factory=list)


class RankingResult(StrictModel):
    status: Literal["ready", "insufficient_verified_courses"]
    selected: list[RankedCourse]
    preview: list[RankedCourse] = Field(default_factory=list)
    eligible_count: int
    excluded_count: int
    warnings: list[str] = Field(default_factory=list)


def _norm(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().casefold())


def _match_hard_constraint(field: str, course: CourseDraft,
                           request: CourseAdvisorInput) -> bool:
    """Fail closed: missing/ambiguous course facts never satisfy a hard rule.

    Only exact, documented equivalences are recognized; numeric prices,
    scheduling and certificate/location are *not* in the current CourseDraft
    structure. Hard rules involving those unavailable facts therefore fail.
    """
    p = request.preferences
    c = request.constraints
    if field == "language":
        actual = _norm(course.language)
        aliases = {"fa": {"fa", "فارسی", "persian", "farsi"},
                   "en": {"en", "english", "انگلیسی"}}
        target = _norm(p.language)
        return bool(actual) and actual in aliases.get(target, {target})
    if field == "format":
        aliases = {
            "in_person": {"in_person", "in person", "حضوری", "classroom"},
            "recorded_online": {"recorded_online", "self paced", "self-paced", "آنلاین ضبط‌شده", "on demand", "on-demand"},
            "live_online": {"live_online", "live online", "آنلاین زنده"},
            "hybrid": {"hybrid", "ترکیبی", "blended"},
        }
        return _norm(course.format) in aliases.get(p.format or "", set())
    if field == "budget":
        if c.budget.mode == "unrestricted":
            return True
        if c.budget.mode == "free":
            return _norm(course.price) in {"free", "رایگان", "0", "0.00", "free of charge"}
        # A limited budget needs structured amount & currency; price string
        # cannot be reliably compared across currencies or payment models.
        return False
    # Not enough structured fields to enforce these hard constraints yet.
    return False


def check_eligibility(review: CourseReview, request: CourseAdvisorInput) -> list[str]:
    reasons = []
    if review.status != "verified":
        reasons.append("source_not_verified")
        return reasons
    if not review.record.name or not review.record.provider:
        reasons.append("missing_identity")
    if canonical_url(review.record.source_url) is None:
        reasons.append("invalid_source_url")
    for field in request.settings.hard_constraints:
        if not _match_hard_constraint(field, review.record, request):
            reasons.append(f"hard_constraint_unverified_or_mismatch:{field}")
    return reasons


def _score(a: FitAssessment) -> tuple[int, dict[str, int]]:
    parts = {key: round(getattr(a, key) * weight / 5)
             for key, weight in WEIGHTS.items()}
    # total is derived from raw weighted scores to avoid accumulation of rounding.
    total = round(sum(getattr(a, key) * weight / 5 for key, weight in WEIGHTS.items()))
    return total, parts


def _preference_adjustment(course: CourseDraft, request: CourseAdvisorInput
                           ) -> tuple[int, list[str]]:
    """Small, explicit soft-preference adjustments. Never disqualify a course.

    Maximum total adjustment is 15 points: budget 7, language 4, format 4.
    The base suitability assessment remains based on topic, level, intent and
    pedagogy. Unknown data receives a smaller deduction than a known mismatch.
    Preferences marked as hard are handled separately by check_eligibility.
    """
    penalty = 0
    notes: list[str] = []
    hard = set(request.settings.hard_constraints)
    if "budget" not in hard and request.constraints.budget.mode in {"free", "limited"}:
        price = _norm(course.price)
        if request.constraints.budget.mode == "free":
            if price in {"free", "رایگان", "0", "0.00", "free of charge"}:
                pass
            elif not price:
                penalty += 3
                notes.append("رایگان‌بودن دوره تأیید نشده است")
            else:
                penalty += 7
                notes.append("این دوره با ترجیح رایگان‌بودن تطابق ندارد")
        elif not price:
            penalty += 3
            notes.append("میزان شهریه مشخص نیست")
        else:
            # Unstructured amounts cannot safely be compared to numeric budget.
            penalty += 3
            notes.append("تطابق شهریه با بودجه هنوز تأیید نشده است")

    if "language" not in hard and request.preferences.language:
        aliases = {
            "fa": {"fa", "فارسی", "persian", "farsi"},
            "en": {"en", "انگلیسی", "english"},
        }
        target = _norm(request.preferences.language)
        actual = _norm(course.language)
        if not actual:
            penalty += 2
            notes.append("زبان دوره مشخص نیست")
        elif actual not in aliases.get(target, {target}):
            penalty += 4
            notes.append("زبان دوره با ترجیح شما یکسان نیست")

    if "format" not in hard and request.preferences.format:
        aliases = {
            "in_person": {"in_person", "in person", "حضوری", "classroom"},
            "recorded_online": {"recorded_online", "self paced", "self-paced",
                                "آنلاین ضبط‌شده", "on demand", "on-demand"},
            "live_online": {"live_online", "live online", "آنلاین زنده"},
            "hybrid": {"hybrid", "ترکیبی", "blended"},
        }
        actual = _norm(course.format)
        if not actual:
            penalty += 2
            notes.append("شیوه برگزاری دوره مشخص نیست")
        elif actual not in aliases.get(request.preferences.format, set()):
            penalty += 4
            notes.append("شیوه برگزاری با ترجیح شما متفاوت است")
    return penalty, notes


def _grounded_explanation(text: str | None, course: CourseDraft) -> str | None:
    """Remove model assertions about facts absent from verified source fields.

    Only narrow, explicit claims are detected; this is a safety backstop in
    addition to the grounded evaluation prompt. When uncertain, return an
    evidence-only fallback instead of reproducing unsupported model prose.
    """
    if text is None:
        return None
    missing_claim_patterns = [
        (course.language, r"فارسی|انگلیسی|زبانِ? (?:آموزش|تدریس)|persian|english"),
        (course.price, r"رایگان|شهریه|بدون هزینه|free (?:course|training)|قیمت"),
        (course.format, r"آنلاین|حضوری|ضبط.?شده|آفلاین|self.paced|online"),
        (course.duration, r"\\d+\\s*(?:ساعت|هفته|ماه)|مدت دوره"),
        # Certificate isn't yet a documented/validated CourseDraft property.
        (None, r"گواهینامه|گواهی[‌ ]?نامه|مدرک معتبر|certificate"),
    ]
    if not any(not fact and re.search(pattern, text, re.IGNORECASE)
               for fact, pattern in missing_claim_patterns):
        return text
    topics = "، ".join(course.topics[:3])
    details = f" سرفصل‌های مستند آن شامل {topics} است." if topics else (
        f" سطح درج‌شده در منبع: {course.level}." if course.level else ""
    )
    return (
        f"دوره «{course.name}» از «{course.provider}» با نیاز آموزشی "
        f"شما مقایسه شده است.{details} سایر ویژگی‌های فاقد شاهد تأییدنشده‌اند."
    )


def rank_courses(reviews: list[CourseReview], assessments: list[FitAssessment],
                 request: CourseAdvisorInput, profile: LearningNeedsProfile,
                 target_count: int = 6) -> RankingResult:
    """Return six diverse, grounded options or an explicit insufficiency state."""
    verify_profile_against_input(profile, request)
    if target_count != 6:
        raise ValueError("MVP contract requires exactly 6 results.")
    assessment_index = {}
    for assessment in assessments:
        key = canonical_url(assessment.course_url)
        if key is None or key in assessment_index:
            raise ValueError("Invalid/duplicate assessment URL.")
        assessment_index[key] = assessment
    eligible: dict[str, RankedCourse] = {}
    excluded = 0
    for review in reviews:
        if check_eligibility(review, request):
            excluded += 1
            continue
        url = canonical_url(review.record.source_url)
        a = assessment_index.get(url)
        if a is None:
            excluded += 1
            continue
        base_score, breakdown = _score(a)
        preference_penalty, preference_notes = _preference_adjustment(
            review.record, request
        )
        score = max(0, base_score - preference_penalty)
        breakdown["preference_adjustment"] = -preference_penalty
        key = course_identity(review.record)
        # Sanitize explanations *after* the deterministic source audit.
        reason = _grounded_explanation(a.reason_fa, review.record)
        limitation = _grounded_explanation(a.limitations_fa, review.record)
        # A synthesized "reason" is not a limitation; prefer just the
        # deterministic and confirmed preference mismatch notes.
        if limitation != a.limitations_fa:
            limitation = None
        combined_limitations = "؛ ".join(
            [value for value in [limitation, *preference_notes] if value]
        ) or None
        ranked = RankedCourse(
            course=review.record, match_score=score,
            reason_fa=reason, score_breakdown=breakdown,
            limitations_fa=combined_limitations,
            unknown_fields=[
                key for key in ("audience", "topics", "level", "duration", "price", "language")
                if not getattr(review.record, key)
            ],
        )
        if key not in eligible or ranked.match_score > eligible[key].match_score:
            eligible[key] = ranked
    ordered = sorted(eligible.values(),
                     key=lambda x: (-x.match_score, _norm(x.course.provider),
                                    _norm(x.course.name), x.course.source_url))
    # First pass: maximize institution diversity without inventing providers.
    selected: list[RankedCourse] = []
    used_providers: set[str] = set()
    for item in ordered:
        provider = _norm(item.course.provider)
        if provider not in used_providers:
            selected.append(item)
            used_providers.add(provider)
        if len(selected) == target_count:
            break
    # Requirement: six courses from different providers, so no same-provider
    # fallback is permitted in the completed report.
    sufficient = len(selected) == target_count
    warnings = [] if sufficient else [
        "Fewer than six eligible, source-backed courses from distinct providers.",
        "Try further search; do not invent courses or relax hard constraints automatically.",
    ]
    return RankingResult(
        status="ready" if sufficient else "insufficient_verified_courses",
        selected=selected if sufficient else [],
        preview=[] if sufficient else selected,
        eligible_count=len(eligible), excluded_count=excluded,
        warnings=warnings,
    )
