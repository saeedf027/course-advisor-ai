"""Step 06: validated beginner learning roadmap data contract.

Rendering belongs to Step 07. The LLM supplies stage content; Python verifies
the stage order and references against the six selected, verified courses.
"""
from __future__ import annotations

from pydantic import Field, model_validator

from app.schemas import CourseAdvisorInput, StrictModel
from Agent.needs_schema import LearningNeedsProfile, verify_profile_against_input
from Tools.rank import RankingResult
from Tools.search import canonical_url


class RoadmapStep(StrictModel):
    step_number: int = Field(ge=1, le=5)
    title: str = Field(min_length=3, max_length=160)
    goal: str = Field(min_length=10, max_length=650)
    skills: list[str] = Field(min_length=1, max_length=5)
    prerequisites: list[str] = Field(default_factory=list, max_length=5)
    # Refer only to actual source URLs returned by Step 05.
    recommended_course_urls: list[str] = Field(min_length=1, max_length=6)
    estimated_weeks_min: int | None = Field(default=None, ge=1, le=52)
    estimated_weeks_max: int | None = Field(default=None, ge=1, le=52)
    estimated_time_note: str | None = Field(default=None, max_length=250)

    @model_validator(mode="after")
    def consistent_duration_and_links(self):
        if (self.estimated_weeks_min is None) != (self.estimated_weeks_max is None):
            raise ValueError("Both duration endpoints must be given together or omitted.")
        if (self.estimated_weeks_min is not None and
                self.estimated_weeks_min > self.estimated_weeks_max):
            raise ValueError("Minimum duration exceeds maximum.")
        normalized = [canonical_url(u) for u in self.recommended_course_urls]
        if any(u is None for u in normalized) or len(set(normalized)) != len(normalized):
            raise ValueError("Course URLs must be valid and distinct within a stage.")
        return self


class LearningRoadmap(StrictModel):
    title: str = Field(min_length=5, max_length=200)
    summary: str = Field(min_length=15, max_length=900)
    audience_level: str = "beginner"
    duration_disclaimer: str = Field(min_length=10, max_length=400)
    steps: list[RoadmapStep] = Field(min_length=3, max_length=5)

    @model_validator(mode="after")
    def check_order(self):
        if self.audience_level != "beginner":
            raise ValueError("Roadmap is only for beginner users in MVP.")
        if [s.step_number for s in self.steps] != list(range(1, len(self.steps) + 1)):
            raise ValueError("Stage numbers must be consecutive, beginning with 1.")
        return self


def validate_roadmap(
    roadmap: LearningRoadmap | None,
    request: CourseAdvisorInput,
    profile: LearningNeedsProfile,
    ranking: RankingResult,
) -> None:
    """Enforce branch gating, source links and course coverage.

    Non-beginners must receive null. A beginner path requires a completed
    six-course selection, and each of those six must be referenced at least
    once somewhere in the roadmap (as options, not necessarily all required).
    """
    verify_profile_against_input(profile, request)
    if not profile.needs_learning_path:
        if roadmap is not None:
            raise ValueError("Non-beginner must not receive a roadmap.")
        return
    if ranking.status != "ready" or len(ranking.selected) != 6:
        if roadmap is not None:
            raise ValueError("Roadmap cannot be generated from incomplete selection.")
        return
    if roadmap is None:
        raise ValueError("Beginner with six selected courses requires a roadmap.")

    selected_urls = [canonical_url(c.course.source_url) for c in ranking.selected]
    if any(url is None for url in selected_urls) or len(set(selected_urls)) != 6:
        raise ValueError("Selected courses must have six unique valid URLs.")
    allowed = set(selected_urls)
    covered = set()
    for step in roadmap.steps:
        for url in step.recommended_course_urls:
            normalized = canonical_url(url)
            if normalized not in allowed:
                raise ValueError(f"Roadmap references an unselected course: {url}")
            covered.add(normalized)
    if covered != allowed:
        raise ValueError("Every selected course must be linked from at least one stage.")


def build_safe_roadmap(
    request: CourseAdvisorInput,
    profile: LearningNeedsProfile,
    ranking: RankingResult,
) -> LearningRoadmap:
    """Construct a conservative, grounded beginner roadmap without model calls.

    Only linked courses selected and verified in the current ranking are used.
    The stage labels describe an advisory sequence, not undocumented course
    curricula, time requirements, or required prerequisites.
    """
    verify_profile_against_input(profile, request)
    if not profile.needs_learning_path or ranking.status != "ready" or len(ranking.selected) != 6:
        raise ValueError("Safe roadmap requires six source-backed beginner course options.")
    courses = ranking.selected
    groups = [courses[:2], courses[2:4], courses[4:6]]
    labels = ["آشنایی و انتخاب نقطه شروع", "تمرین و توسعه مهارت", "پروژه و کاربرد عملی"]
    goals = [
        "ابتدا سرفصل‌های مستند گزینه‌های این مرحله را بررسی کنید و مباحث مقدماتی را انتخاب کنید.",
        "مطالبی را که در دوره‌های منتخب واقعاً ارائه می‌شوند تمرین کنید و آموخته‌های خود را مرور کنید.",
        "با مهارت‌های آموخته‌شده یک تمرین یا پروژه کوچک متناسب با هدف آموزشی خود تعریف کنید.",
    ]
    steps = [
        RoadmapStep(
            step_number=i + 1,
            title=labels[i],
            goal=goals[i],
            skills=["بررسی محتوای دوره‌ها", "تمرین و خودارزیابی"],
            prerequisites=[] if i == 0 else ["مرور مهارت‌های مرحله قبل"],
            recommended_course_urls=[c.course.source_url for c in group],
            estimated_weeks_min=None,
            estimated_weeks_max=None,
            estimated_time_note="این مراحل پیشنهادی‌اند؛ مدت و ترتیب دقیق از منبع دوره تأیید نشده است.",
        )
        for i, group in enumerate(groups)
    ]
    roadmap = LearningRoadmap(
        title=f"مسیر پیشنهادی یادگیری {request.learning_request.topic}",
        summary="این مسیر یک سازمان‌دهی پیشنهادی برای بررسی دوره‌های معتبر است؛ همه دوره‌ها الزامی نیستند.",
        duration_disclaimer="زمان‌بندی و ترتیب مراحل تخمینی است و جایگزین برنامه رسمی مؤسسه‌ها نیست.",
        steps=steps,
    )
    validate_roadmap(roadmap, request, profile, ranking)
    return roadmap
