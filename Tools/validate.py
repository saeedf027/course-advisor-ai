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
    """Normalize typographic differences, not meaning.

    The same literal words must appear together in the same source page.
    This handles Unicode presentation forms, Persian/Arabic variants,
    zero-width joiners and line breaks that often appear in extracted HTML.
    No fuzzy/semantic matching is performed.
    """
    text = unicodedata.normalize("NFKC", value)
    text = text.translate(str.maketrans({"ي": "ی", "ى": "ی", "ك": "ک"}))
    text = re.sub(r"[\\u200c\\u200d\\u200e\\u200f\\ufeff]", " ", text)
    text = re.sub(r"\\s+", " ", text)
    return text.strip().casefold()


def review_course(draft: CourseDraft, source_content: str,
                  extracted_url: str) -> CourseReview:
    """Conservative verification against one fetched source.

    Verification here means *required facts have explicit text evidence*,
    not that an independent institution audited the provider.
    """
    reasons: list[str] = []
    src = canonical_url(extracted_url)
    claimed = canonical_url(draft.source_url)
    if src is None or claimed is None or src != claimed:
        return CourseReview(status="rejected", record=draft,
                            reasons=["Source URL differs from extracted page."])
    if not source_content.strip():
        return CourseReview(status="rejected", record=draft,
                            reasons=["Source page is empty."])
    required = ["name", "provider", "audience", "topics"]
    missing = [f for f in required if not getattr(draft, f)]
    if not draft.level and not draft.duration:
        missing.append("level_or_duration")
    evidence_fields: set[str] = set()
    normalized_content = normalize_evidence_text(source_content)
    for ev in draft.evidence:
        if (canonical_url(ev.source_url) != src or
                normalize_evidence_text(ev.quote) not in normalized_content):
            reasons.append(f"Unmatched evidence for {ev.field}.")
        else:
            evidence_fields.add(ev.field)
    for field in required:
        if field not in evidence_fields:
            missing.append(f"evidence:{field}")
    if not ({"level", "duration"} & evidence_fields):
        missing.append("evidence:level_or_duration")
    # Explicit contradictions are handled later by cross-source validation.
    # Missing optional facts are unknown, NOT filled in by the LLM.
    if reasons:
        return CourseReview(status="rejected", record=draft, reasons=reasons,
                            missing_fields=missing)
    if missing:
        return CourseReview(status="incomplete", record=draft, missing_fields=missing)
    return CourseReview(status="verified", record=draft)


def course_identity(draft: CourseDraft) -> str:
    """Coarse duplicate key for the same offering, including URL variants."""
    if draft.name and draft.provider:
        def normalize(s: str) -> str:
            return " ".join(s.casefold().split())
        return f"{normalize(draft.provider)}::{normalize(draft.name)}"
    return canonical_url(draft.source_url) or draft.source_url
