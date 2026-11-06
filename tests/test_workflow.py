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
    assert result.diagnostics["eligible_before_evaluation"] == 3
    assert result.diagnostics["evaluation_errors"] == 0
    assert len(result.ranking.preview) == 3
    assert "پیشنهادهای اولیه" in result.report_html

def test_parallel_extraction_is_bounded_and_reduces_wall_clock():
    class ConcurrentAgent(FakeAgent):
        def __init__(self):
            self.active = 0
            self.peak = 0
        async def complete(self, *, prompt_file, payload, schema, retries=1):
            if prompt_file == "course_extraction.md":
                self.active += 1
                self.peak = max(self.peak, self.active)
                await asyncio.sleep(0.03)
                try:
                    return await super().complete(
                        prompt_file=prompt_file, payload=payload,
                        schema=schema, retries=retries
                    )
                finally:
                    self.active -= 1
            return await super().complete(
                prompt_file=prompt_file, payload=payload,
                schema=schema, retries=retries
            )

    agent = ConcurrentAgent()
    result = asyncio.run(Pipeline(
        agent=agent, search=fake_search, extract=fake_extract,
        llm_concurrency=2,
    ).run(input_request(), demo=True))
    assert result.status == "ready"
    assert agent.peak == 2


def test_pipeline_rejects_unbounded_limits():
    import pytest
    with pytest.raises(ValueError):
        Pipeline(llm_concurrency=5)
    with pytest.raises(ValueError):
        Pipeline(agent_timeout_seconds=2)


def test_partial_results_are_scored_before_six_providers():
    class CountingAgent(FakeAgent):
        def __init__(self):
            self.evaluation_calls = 0
        async def complete(self, *, prompt_file, payload, schema, retries=1):
            if prompt_file == "course_evaluation.md":
                self.evaluation_calls += 1
            return await super().complete(
                prompt_file=prompt_file, payload=payload,
                schema=schema, retries=retries
            )

    agent = CountingAgent()

    async def only_three(batch, max_urls):
        chosen = {c.url for c in batch.candidates}
        return ExtractionBatch(
            pages=[page(i) for i in range(3) if page(i).url in chosen]
        )

    result = asyncio.run(Pipeline(
        agent=agent, search=fake_search, extract=only_three,
    ).run(input_request(), demo=True))
    assert result.status == "insufficient_verified_courses"
    assert result.ranking.selected == []
    assert len(result.ranking.preview) == 3
    assert agent.evaluation_calls == 3
    assert result.roadmap is None
    assert result.diagnostics["discovery_rounds"] == 1

def test_source_audit_distinguishes_not_course_from_incomplete():
    class RejectAllAgent(FakeAgent):
        async def complete(self, *, prompt_file, payload, schema, retries=1):
            if prompt_file == "course_extraction.md":
                return CourseExtraction(
                    is_course=False, course=None,
                    rejection_reason="listing_or_search"
                )
            return await super().complete(
                prompt_file=prompt_file, payload=payload,
                schema=schema, retries=retries
            )

    result = asyncio.run(Pipeline(
        agent=RejectAllAgent(), search=fake_search, extract=fake_extract
    ).run(input_request(), demo=True))
    assert result.status == "insufficient_verified_courses"
    assert result.diagnostics["not_course_page"] == 6
    assert len(result.candidate_audit) == 6
    assert all(item["status"] == "not_course_page" for item in result.candidate_audit)
    assert all(item["reason"] == "listing_or_search" for item in result.candidate_audit)
    assert all("url" in item and "title" in item for item in result.candidate_audit)


def test_source_audit_marks_not_selected_due_to_limit():
    result = asyncio.run(Pipeline(
        agent=FakeAgent(), search=fake_search, extract=fake_extract,
        max_pages=3
    ).run(input_request(), demo=True))
    assert len(result.candidate_audit) == 6
    assert sum(c["selected_for_extraction"] for c in result.candidate_audit) == 3
    assert sum(c["status"] == "not_selected_budget" for c in result.candidate_audit) == 3

def test_adaptive_second_round_recovers_six_unique_courses():
    calls = []
    async def expanded_search(plan):
        return SearchBatch(
            candidates=[
                CandidatePage(url=f"https://example.org/course/{i}",
                              title=f"Course {i}", snippet="Mock result")
                for i in range(9)
            ],
            searched_queries=[p.query for p in plan.queries],
            total_results_before_dedup=9,
        )

    async def selective_extract(batch, max_urls):
        calls.append([c.url for c in batch.candidates])
        # Pages 0-2 are all non-returning, so first six produce only three
        # verified courses; the next three complete a six-provider set.
        selected = {
            c.url for c in batch.candidates
        }
        return ExtractionBatch(pages=[
            page(i) for i in range(3, 9) if page(i).url in selected
        ])

    result = asyncio.run(Pipeline(
        agent=FakeAgent(), search=expanded_search,
        extract=selective_extract, max_pages=9,
    ).run(input_request(), demo=True))
    assert result.status == "ready"
    assert len(result.ranking.selected) == 6
    assert result.roadmap is not None
    assert len(calls) == 2
    assert len(calls[0]) == 6
    assert len(calls[1]) == 3
    assert result.diagnostics["pages_attempted"] == 9
    assert result.diagnostics["discovery_rounds"] == 2


def test_adaptive_rounds_respect_strict_total_page_budget():
    calls = []
    async def many_results(plan):
        return SearchBatch(
            candidates=[
                CandidatePage(url=f"https://example.org/course/{i}",
                              title=f"Course {i}", snippet="Mock result")
                for i in range(20)
            ], searched_queries=[], total_results_before_dedup=20,
        )

    async def no_pages(batch, max_urls):
        calls.extend(c.url for c in batch.candidates)
        return ExtractionBatch()

    result = asyncio.run(Pipeline(
        agent=FakeAgent(), search=many_results, extract=no_pages,
        max_pages=8,
    ).run(input_request(), demo=True))
    assert result.status == "insufficient_verified_courses"
    assert result.diagnostics["pages_attempted"] == 8
    assert result.diagnostics["discovery_rounds"] == 2
    assert len(calls) == 8
    assert len(result.ranking.preview) == 0
