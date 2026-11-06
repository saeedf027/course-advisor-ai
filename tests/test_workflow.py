"""Offline Stage 08 integration tests using injected fakes."""
import asyncio

from Agent.extraction_schema import CourseExtraction
from Agent.needs_schema import LearningNeedsProfile
from app.schemas import CourseAdvisorInput
from Tools.extract import ExtractionBatch, ExtractedPage
from Tools.search import SearchBatch, CandidatePage
from Tools.rank import FitAssessment
from Tools.roadmap import LearningRoadmap
from Tools.validate import CourseDraft, Evidence
from Workflow.runner import Pipeline


def input_request():
    return CourseAdvisorInput.model_validate({
        "learning_request": {"topic": "Data Analysis", "level": "beginner"}
    })


def page(i):
    url = f"https://example.org/course/{i}"
    return ExtractedPage(
        url=url,
        raw_content=(
            f"Title: Data Course {i}. Provider: Institute {i}. "
            f"Audience: Beginners. Topics: spreadsheet charts. Level: Beginner."
        ),
    )


class FakeAgent:
    async def complete(self, *, prompt_file, payload, schema, retries=1):
        if prompt_file == "needs_analysis.md":
            return LearningNeedsProfile.model_validate({
                "topic": "Data Analysis", "resolved_level": "beginner",
                "level_source": "explicit", "level_confidence": "high",
                "learning_intent": "Learn entry-level data analysis",
                "search_topics": ["Data Analysis", "Spreadsheet analysis", "Charts"],
                "needs_learning_path": True,
            })
        if prompt_file == "course_extraction.md":
            url = payload["source_url"]
            i = int(url.rsplit("/", 1)[-1])
            draft = CourseDraft(
                name=f"Data Course {i}", provider=f"Institute {i}",
                audience="Beginners", topics=["spreadsheet charts"], level="Beginner",
                source_url=url, evidence=[
                    Evidence(field="name", source_url=url, quote=f"Data Course {i}"),
                    Evidence(field="provider", source_url=url, quote=f"Institute {i}"),
                    Evidence(field="audience", source_url=url, quote="Beginners"),
                    Evidence(field="topics", source_url=url, quote="spreadsheet charts"),
                    Evidence(field="level", source_url=url, quote="Level: Beginner"),
                ],
            )
            return CourseExtraction(is_course=True, course=draft)
        if prompt_file == "course_evaluation.md":
            url = payload["course"]["source_url"]
            return FitAssessment(course_url=url, topic=5, level=5, intent=5,
                                 pedagogy=4, reason_fa="این دوره با هدف آموزشی و سطح کاربر تناسب دارد.")
        if prompt_file == "roadmap_generation.md":
            urls = [r["course"]["source_url"] for r in payload["selected_courses"]]
            return LearningRoadmap.model_validate({
                "title": "مسیر یادگیری تحلیل داده",
                "summary": "یک مسیر آموزشی مقدماتی همراه با دوره‌های منتخب",
                "duration_disclaimer": "مدت زمان یادگیری تخمینی است و به تمرین بستگی دارد.",
                "steps": [{
                    "step_number": j+1, "title": f"گام {j+1} یادگیری داده",
                    "goal": "آموختن مفاهیم و تمرین کاربردهای مرتبط با داده",
                    "skills": ["آموزش", "تمرین"],
                    "recommended_course_urls": urls[2*j:2*j+2],
                } for j in range(3)],
            })
        raise AssertionError(prompt_file)


async def fake_search(plan):
    return SearchBatch(
        candidates=[CandidatePage(
            url=f"https://example.org/course/{i}", title=f"Course {i}",
            snippet="Mock search hit",
        ) for i in range(6)],
        searched_queries=[q.query for q in plan.queries],
        total_results_before_dedup=6,
    )


async def fake_extract(batch, max_urls):
    return ExtractionBatch(pages=[page(i) for i in range(6)])


def test_pipeline_with_six_mock_courses_and_roadmap():
    pipeline = Pipeline(agent=FakeAgent(), search=fake_search, extract=fake_extract)
    result = asyncio.run(pipeline.run(input_request(), demo=True))
    assert result.status == "ready"
    assert len(result.ranking.selected) == 6
    assert result.roadmap is not None
    assert result.report_html.count('class="course"') == 6
    assert result.report_html.count('class="step"') == 3
    assert "فقط داده نمایشی" in result.report_html


def test_insufficient_mock_pages_do_not_create_fake_results():
    async def fewer_search(plan):
        batch = await fake_search(plan)
        return batch.model_copy(update={"candidates": batch.candidates[:3]})
    async def fewer_extract(batch, max_urls):
        return ExtractionBatch(pages=[page(i) for i in range(3)])
    pipeline = Pipeline(agent=FakeAgent(), search=fewer_search, extract=fewer_extract)
    result = asyncio.run(pipeline.run(input_request(), demo=True))
    assert result.status == "insufficient_verified_courses"
    assert result.roadmap is None
    assert "نتیجه ناکافی است" in result.report_html
    assert result.diagnostics is not None
    assert sum(result.diagnostics.values()) == 0
