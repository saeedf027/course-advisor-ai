"""WAT orchestrator: bounded concurrent extraction and evaluation.

Search and source extraction are independent of LLM inference. Course facts
must be evidence-backed; strict constraints are never relaxed to fill six slots.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from app.schemas import CourseAdvisorInput
from Agent.client import AvalAIClient, AgentCallError
from Agent.extraction_schema import CourseExtraction
from Agent.needs_schema import LearningNeedsProfile, verify_profile_against_input
from Tools.search import build_search_plan, run_search, SearchBatch, canonical_url
from Tools.extract import extract_candidates, ExtractionBatch, ExtractedPage
from Tools.validate import CourseReview, review_course
from Tools.rank import (
    FitAssessment, rank_courses, RankingResult, check_eligibility
)
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
    diagnostics: dict[str, int] | None = None


class Pipeline:
    """Dependency-injected workflow with hard limits on LLM concurrency and time."""

    def __init__(
        self, agent=None, search=None, extract=None, *,
        max_pages: int = 8, llm_concurrency: int = 3,
        agent_timeout_seconds: float = 30.0,
    ):
        if not 1 <= max_pages <= 30:
            raise ValueError("max_pages must be 1..30")
        if not 1 <= llm_concurrency <= 4:
            raise ValueError("llm_concurrency must be 1..4")
        if not 5 <= agent_timeout_seconds <= 90:
            raise ValueError("agent_timeout_seconds must be 5..90")
        self.agent = agent
        self.search = search or run_search
        self.extract = extract or extract_candidates
        self.max_pages = max_pages
        self.llm_concurrency = llm_concurrency
        self.agent_timeout_seconds = agent_timeout_seconds

    def _agent(self):
        if self.agent is None:
            load_dotenv(ROOT / ".env")
            self.agent = AvalAIClient()
        return self.agent

    async def run(self, request: CourseAdvisorInput, *, demo: bool = False) -> PipelineResult:
        agent = self._agent()
        semaphore = asyncio.Semaphore(self.llm_concurrency)
        diagnostics = {
            "agent_extraction_errors": 0, "not_course_page": 0,
            "incomplete_source": 0, "rejected_source": 0,
            "evaluation_errors": 0, "assessment_url_mismatch": 0,
            "hard_constraint_excluded": 0, "evaluations_skipped_insufficient": 0,
            "eligible_before_evaluation": 0,
        }

        async def ask(prompt_file, payload, schema):
            # One API attempt per stage. This avoids 55s x retry x N pages.
            async with semaphore:
                try:
                    return await asyncio.wait_for(
                        agent.complete(
                            prompt_file=prompt_file, payload=payload,
                            schema=schema, retries=0,
                        ),
                        timeout=self.agent_timeout_seconds,
                    )
                except asyncio.TimeoutError as exc:
                    raise AgentCallError("Timed out waiting for LLM response") from exc

        profile = await ask(
            "needs_analysis.md",
            {"request": request.model_dump(mode="json")},
            LearningNeedsProfile,
        )
        verify_profile_against_input(profile, request)
        plan = build_search_plan(request, profile)
        search_result: SearchBatch = await self.search(plan)
        search_result = search_result.model_copy(
            update={"candidates": search_result.candidates[:self.max_pages]}
        )
        extraction: ExtractionBatch = await self.extract(
            search_result, max_urls=self.max_pages
        )

        async def extract_one(page: ExtractedPage):
            try:
                response = await ask(
                    "course_extraction.md",
                    {"source_url": page.url, "source_content": page.raw_content},
                    CourseExtraction,
                )
            except AgentCallError:
                return ("agent_extraction_errors", None)
            if not response.is_course or response.course is None:
                return ("not_course_page", None)
            review = review_course(response.course, page.raw_content, page.url)
            if review.status == "incomplete":
                return ("incomplete_source", None)
            if review.status == "rejected":
                return ("rejected_source", None)
            return ("verified", review)

        extraction_results = await asyncio.gather(
            *(extract_one(p) for p in extraction.pages[:self.max_pages])
        )
        reviews: list[CourseReview] = []
        for category, record in extraction_results:
            if category == "verified":
                reviews.append(record)
            else:
                diagnostics[category] += 1

        eligible = []
        for review in reviews:
            if check_eligibility(review, request):
                diagnostics["hard_constraint_excluded"] += 1
            else:
                eligible.append(review)
        diagnostics["eligible_before_evaluation"] = len(eligible)

        # Check distinct providers before spending on one evaluation call
        # per course. Incomplete sets cannot produce a six-provider report.
        distinct_providers = {
            " ".join((r.record.provider or "").casefold().split())
            for r in eligible if r.record.provider
        }
        assessments: list[FitAssessment] = []
        if len(distinct_providers) < 6:
            diagnostics["evaluations_skipped_insufficient"] = len(eligible)
        else:
            async def evaluate_one(review: CourseReview):
                try:
                    result = await ask(
                        "course_evaluation.md",
                        {
                            "request": request.model_dump(mode="json"),
                            "needs": profile.model_dump(mode="json"),
                            "course": review.record.model_dump(mode="json"),
                        },
                        FitAssessment,
                    )
                except AgentCallError:
                    return ("evaluation_errors", None)
                if canonical_url(result.course_url) != canonical_url(review.record.source_url):
                    return ("assessment_url_mismatch", None)
                return ("ok", result)

            evaluations = await asyncio.gather(
                *(evaluate_one(r) for r in eligible)
            )
            for category, assessment in evaluations:
                if category == "ok":
                    assessments.append(assessment)
                else:
                    diagnostics[category] += 1

        # rank_courses itself rechecks hard constraints and source eligibility.
        ranking = rank_courses(reviews, assessments, request, profile)
        roadmap: LearningRoadmap | None = None
        if ranking.status == "ready" and profile.needs_learning_path:
            roadmap = await ask(
                "roadmap_generation.md",
                {
                    "request": request.model_dump(mode="json"),
                    "needs": profile.model_dump(mode="json"),
                    "selected_courses": [
                        item.model_dump(mode="json") for item in ranking.selected
                    ],
                },
                LearningRoadmap,
            )
            validate_roadmap(roadmap, request, profile, ranking)

        html = render_report(request, profile, ranking, roadmap, demo=demo)
        return PipelineResult(
            status=ranking.status, report_html=html, ranking=ranking,
            roadmap=roadmap, searched_pages=len(search_result.candidates),
            extracted_pages=len(extraction.pages),
            reviewed_courses=len(reviews), diagnostics=diagnostics,
        )


def run_from_file(input_path: str, output_path: str) -> PipelineResult:
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
