"""Step 08 — orchestrated Course Advisor AI MVP.

A complete run requires live Tavily + OpenRouter credentials. Offline tests
inject collaborators and do not perform network calls.
"""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from app.schemas import CourseAdvisorInput
from Agent.client import OpenRouterClient, AgentCallError
from Agent.extraction_schema import CourseExtraction
from Agent.needs_schema import LearningNeedsProfile, verify_profile_against_input
from Tools.search import build_search_plan, run_search, SearchBatch
from Tools.extract import extract_candidates, ExtractionBatch
from Tools.validate import CourseReview, review_course
from Tools.rank import FitAssessment, rank_courses, RankingResult
from Tools.roadmap import LearningRoadmap, validate_roadmap
from Tools.render import render_report, save_report

ROOT = Path(__file__).resolve().parents[1]


class PipelineError(RuntimeError):
    pass


@dataclass
class PipelineResult:
    status: str
    report_html: str
    ranking: RankingResult
    roadmap: LearningRoadmap | None
    searched_pages: int
    extracted_pages: int
    reviewed_courses: int


class Pipeline:
    """Dependency-injected workflow for budgeted, testable execution."""

    def __init__(self, agent=None, search=None, extract=None, *, max_pages: int = 20):
        if not 1 <= max_pages <= 30:
            raise ValueError("max_pages must be 1..30")
        self.agent = agent
        self.search = search or run_search
        self.extract = extract or extract_candidates
        self.max_pages = max_pages

    def _agent(self):
        if self.agent is None:
            load_dotenv(ROOT / ".env")
            self.agent = OpenRouterClient()
        return self.agent

    async def run(self, request: CourseAdvisorInput, *, demo: bool = False) -> PipelineResult:
        """Run once with bounded search/extraction; fail clearly if insufficient."""
        agent = self._agent()
        profile = await agent.complete(
            prompt_file="needs_analysis.md", payload={"request": request.model_dump(mode="json")},
            schema=LearningNeedsProfile,
        )
        verify_profile_against_input(profile, request)
        plan = build_search_plan(request, profile)
        search_result: SearchBatch = await self.search(plan)
        # Truncate before extraction to bound tokens, time and cost.
        search_result = search_result.model_copy(update={
            "candidates": search_result.candidates[:self.max_pages]
        })
        extraction: ExtractionBatch = await self.extract(
            search_result, max_urls=self.max_pages
        )
        # Process the fetched content only. Never prompt with arbitrary direct URL fetching.
        review_list: list[CourseReview] = []
        pages_by_url = {p.url: p for p in extraction.pages}
        for page in extraction.pages[:self.max_pages]:
            try:
                result = await agent.complete(
                    prompt_file="course_extraction.md",
                    payload={"source_url": page.url, "source_content": page.raw_content},
                    schema=CourseExtraction,
                )
            except AgentCallError:
                continue
            if not result.is_course or result.course is None:
                continue
            review = review_course(result.course, page.raw_content, page.url)
            if review.status == "verified":
                review_list.append(review)

        assessments: list[FitAssessment] = []
        for review in review_list:
            try:
                assessment = await agent.complete(
                    prompt_file="course_evaluation.md",
                    payload={
                        "request": request.model_dump(mode="json"),
                        "needs": profile.model_dump(mode="json"),
                        "course": review.record.model_dump(mode="json"),
                    },
                    schema=FitAssessment,
                )
                if assessment.course_url == review.record.source_url:
                    assessments.append(assessment)
            except AgentCallError:
                continue
        ranking = rank_courses(review_list, assessments, request, profile)
        roadmap: LearningRoadmap | None = None
        if ranking.status == "ready" and profile.needs_learning_path:
            roadmap = await agent.complete(
                prompt_file="roadmap_generation.md",
                payload={
                    "request": request.model_dump(mode="json"),
                    "needs": profile.model_dump(mode="json"),
                    "selected_courses": [
                        item.model_dump(mode="json") for item in ranking.selected
                    ],
                },
                schema=LearningRoadmap,
            )
            validate_roadmap(roadmap, request, profile, ranking)
        html = render_report(request, profile, ranking, roadmap, demo=demo)
        return PipelineResult(
            status=ranking.status, report_html=html, ranking=ranking,
            roadmap=roadmap, searched_pages=len(search_result.candidates),
            extracted_pages=len(extraction.pages),
            reviewed_courses=len(review_list),
        )


def run_from_file(input_path: str, output_path: str) -> PipelineResult:
    """CLI entrypoint: input JSON file -> output HTML file."""
    import json
    from app.schemas import CourseAdvisorInput
    load_dotenv(ROOT / ".env")
    request = CourseAdvisorInput.model_validate_json(
        Path(input_path).read_text(encoding="utf-8")
    )
    result = asyncio.run(Pipeline().run(request))
    save_report(result.report_html, output_path)
    return result


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Course Advisor AI end-to-end runner")
    parser.add_argument("--input", default="tests/sample_input.json")
    parser.add_argument("--output", default="outputs/report.html")
    args = parser.parse_args()
    outcome = run_from_file(args.input, args.output)
    print(f"Status: {outcome.status}; saved report to {args.output}")
