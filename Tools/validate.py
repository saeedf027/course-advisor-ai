"""Step 04B — deterministic source and course-record quality gates.

CourseDraft is constructed by a *future* grounded extraction Agent using the
retrieved page text. This module does NOT invent or infer any facts.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, model_validator
from app.schemas import StrictModel
from Tools.search import canonical_url

FactField = Literal[
    "name", "provider", "level", "duration", "audience", "topics",
    "language", "format", "price"
]


class Evidence(StrictModel):
    field: FactField
    source_url: str
    quote: str = Field(min_length=3, max_length=700)


class CourseDraft(StrictModel):
    name: str | None = None
    provider: str | None = None
    level: str | None = None
    duration: str | None = None
    audience: str | None = None
    topics: list[str] = Field(default_factory=list)
    language: str | None = None
    format: str | None = None
    price: str | None = None
    source_url: str
    evidence: list[Evidence] = Field(default_factory=list)


class CourseReview(StrictModel):
    status: Literal["verified", "incomplete", "rejected"]
    record: CourseDraft
    missing_fields: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)


def normalize_evidence_text(value: str) -> str:
    """Normalize typography, without fuzzy or semantic source matching."""
    text = unicodedata.normalize("NFKC", value)
    text = text.translate(str.maketrans({"ي": "ی", "ى": "ی", "ك": "ک"}))
    text = re.sub(r"[\u200c\u200d\u200e\u200f\ufeff]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip().casefold()


def review_course(draft: CourseDraft, source_content: str,
                  extracted_url: str) -> CourseReview:
    """Ground core identity strictly, while allowing absent optional fields.

    'verified' means a specific course identity is source-backed, not that
    every descriptive attribute is known, or the course is a good fit.
    Optional claims without matching evidence are removed rather than
    accepted. Unknowns can be disclosed/scored neutrally downstream.
    """
    src = canonical_url(extracted_url)
    claimed = canonical_url(draft.source_url)
    if src is None or claimed is None or src != claimed:
        return CourseReview(status="rejected", record=draft,
                            reasons=["Source URL differs from extracted page."])
    if not source_content.strip():
        return CourseReview(status="rejected", record=draft,
                            reasons=["Source page is empty."])

    normalized_content = normalize_evidence_text(source_content)
    valid_evidence: dict[str, list[Evidence]] = {}
    unsupported: list[str] = []
    for ev in draft.evidence:
        if (canonical_url(ev.source_url) == src
                and normalize_evidence_text(ev.quote) in normalized_content):
            valid_evidence.setdefault(ev.field, []).append(ev)
        else:
            unsupported.append(ev.field)

    # We must be certain this is a named offering belonging to a provider.
    missing_core = [
        field for field in ("name", "provider")
        if not getattr(draft, field) or field not in valid_evidence
    ]
    if missing_core:
        return CourseReview(status="incomplete", record=draft,
                            missing_fields=missing_core,
                            reasons=["Course identity needs literal source evidence."])

    # Neither title-only pages nor empty listings qualify: require at least
    # one verifiable syllabus/level/duration fact.
    if not any(field in valid_evidence and getattr(draft, field)
               for field in ("topics", "level", "duration")):
        return CourseReview(status="incomplete", record=draft,
                            missing_fields=["topics_or_level_or_duration"],
                            reasons=["No verifiable educational details."])

    cleaned = draft.model_copy(deep=True)
    dropped: list[str] = []
    for field in ("audience", "topics", "level", "duration", "language",
                  "format", "price"):
        if getattr(cleaned, field) and field not in valid_evidence:
            setattr(cleaned, field, [] if field == "topics" else None)
            dropped.append(field)
    cleaned.evidence = [
        ev for values in valid_evidence.values() for ev in values
    ]

    return CourseReview(
        status="verified", record=cleaned,
        missing_fields=sorted(set(dropped + [
            field for field in ("audience", "topics", "level", "duration")
            if not getattr(cleaned, field)
        ])),
        reasons=(
            ["Unsupported optional claims omitted: " + ",".join(sorted(set(dropped)))]
            if dropped else []
        ),
    )


def course_identity(draft: CourseDraft) -> str:
    """Coarse duplicate key for the same offering, including URL variants."""
    if draft.name and draft.provider:
        def normalize(s: str) -> str:
            return " ".join(s.casefold().split())
        return f"{normalize(draft.provider)}::{normalize(draft.name)}"
    return canonical_url(draft.source_url) or draft.source_url
