"""Envelope for grounded course extraction from one source page."""
from pydantic import model_validator
from app.schemas import StrictModel
from Tools.validate import CourseDraft


class CourseExtraction(StrictModel):
    is_course: bool
    course: CourseDraft | None = None

    @model_validator(mode="after")
    def course_presence(self):
        if self.is_course and self.course is None:
            raise ValueError("A course page requires a course record.")
        if not self.is_course and self.course is not None:
            raise ValueError("A non-course page must not include a course record.")
        return self
