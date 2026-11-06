"""Envelope for grounded course extraction from one source page."""
from typing import Literal

from pydantic import model_validator
from app.schemas import StrictModel
from Tools.validate import CourseDraft

RejectionReason = Literal[
    "category_page", "article_or_blog", "listing_or_search", "unrelated",
    "insufficient_single_course_signal", "unknown",
]


class CourseExtraction(StrictModel):
    is_course: bool
    course: CourseDraft | None = None
    rejection_reason: RejectionReason | None = None

    @model_validator(mode="after")
    def course_presence(self):
        if self.is_course and self.course is None:
            raise ValueError("A course page requires a course record.")
        if self.is_course and self.rejection_reason is not None:
            raise ValueError("A course record must not have a rejection reason.")
        if not self.is_course and self.course is not None:
            raise ValueError("A non-course page must not include a course record.")
        return self
