"""Structured output contract for the needs-analysis LLM (Pydantic v2)."""
from typing import Literal
from pydantic import Field, model_validator
from app.schemas import StrictModel


HardConstraint = Literal[
    "language", "format", "learning_style", "certificate",
    "budget", "location", "weekly_hours", "duration"
]


class LearningNeedsProfile(StrictModel):
    topic: str = Field(min_length=2, max_length=200)
    resolved_level: Literal["beginner", "intermediate", "advanced", "unknown"]
    level_source: Literal["explicit", "inferred", "unknown"]
    level_confidence: Literal["high", "medium", "low"]
    learning_intent: str = Field(min_length=2, max_length=1000)
    search_topics: list[str] = Field(min_length=3, max_length=8)
    suggested_prerequisites: list[str] = Field(default_factory=list, max_length=8)
    hard_constraints: list[HardConstraint] = Field(default_factory=list)
    needs_learning_path: bool
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def consistent_level(self):
        if self.resolved_level == "unknown" and self.level_source != "unknown":
            raise ValueError("Unknown level must have unknown source.")
        if self.resolved_level != "unknown" and self.level_source == "unknown":
            raise ValueError("Known level needs explicit or inferred source.")
        if self.needs_learning_path != (self.resolved_level == "beginner"):
            raise ValueError("Learning path must be requested exactly for beginner level.")
        if len(self.hard_constraints) != len(set(self.hard_constraints)):
            raise ValueError("Duplicated hard constraints.")
        return self


def verify_profile_against_input(profile: LearningNeedsProfile, request) -> None:
    """Deterministically enforce facts the LLM is forbidden to rewrite."""
    if profile.topic != request.learning_request.topic:
        raise ValueError("Agent changed the user's topic.")
    if profile.hard_constraints != request.settings.hard_constraints:
        raise ValueError("Agent changed hard constraints.")
    explicit = request.learning_request.level
    if explicit is not None:
        if profile.resolved_level != explicit.value or profile.level_source != "explicit":
            raise ValueError("Agent overrode the user's explicit level.")
    elif profile.level_source == "explicit":
        raise ValueError("Agent claimed an explicit level that was not supplied.")
