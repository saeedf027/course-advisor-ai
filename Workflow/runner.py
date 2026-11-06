"""WAT orchestrator: bounded concurrent extraction and evaluation.

Search and source extraction are independent of LLM inference. Course facts
must be evidence-backed; strict constraints are never relaxed to fill six slots.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

from app.schemas import CourseAdvisorInput
from Agent.client import AvalAIClient, AgentCallError
from Agent.extraction_schema import CourseExtraction
from Agent.needs_schema import LearningNeedsProfile, verify_profile_against_input
from Tools.search import (build_search_plan, run_search, SearchBatch, canonical_url,
                          prioritize_candidates, candidate_priority)
from Tools.extract import extract_candidates, ExtractionBatch, ExtractedPage
from Tools.validate import CourseReview, review_course, recover_provider_from_page
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
    candidate_audit: list[dict] = field(default_factory=list)


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
            "eligible_before_evaluation": 0, "discovery_rounds": 0,
            "pages_attempted": 0,
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
        all_candidates = search_result.candidates
        # Rank and diversify the full result pool once. The first six URLs
        # form round one; later rounds use only remaining search results.
        ordered = prioritize_candidates(
            all_candidates, len(all_candidates),
            topic=request.learning_request.topic,
        ) if all_candidates else []
        page_budget = min(self.max_pages, len(ordered))
        selected_urls: set[str] = set()
        audit_by_url: dict[str, dict] = {}
        candidate_audit: list[dict] = []
        for candidate in all_candidates[:40]:
            row = {
                "url": candidate.url.split("?")[0],
                "title": candidate.title[:160],
                "priority_score": candidate_priority(candidate, request.learning_request.topic),
                "selected_for_extraction": False,
                "status": "not_selected_budget",
                "reason": None,
            }
            candidate_audit.append(row)
            audit_by_url[canonical_url(candidate.url)] = row

        search_by_url = {canonical_url(c.url): c for c in all_candidates}
        reviews: list[CourseReview] = []
        eligible: list[CourseReview] = []
        fetched_count = 0
        rounds = 0

        async def extract_one(page: ExtractedPage):
            candidate = search_by_url.get(canonical_url(page.url))
            try:
                response = await ask(
                    "course_extraction.md",
                    {
                        "source_url": page.url,
                        "source_content": page.raw_content,
                        "search_title": candidate.title if candidate else "",
                        "search_snippet": candidate.snippet[:450] if candidate else "",
                    },
                    CourseExtraction,
                )
            except AgentCallError:
                return ("agent_extraction_errors", None, "invalid_agent_response")
            if not response.is_course or response.course is None:
                return ("not_course_page", None, response.rejection_reason or "unknown")
            candidate_title = candidate.title if candidate else ""
            draft = recover_provider_from_page(
                response.course, page.raw_content, candidate_title
            )
            review = review_course(draft, page.raw_content, page.url)
            if review.status == "incomplete":
                return ("incomplete_source", None, ",".join(review.missing_fields[:8]))
            if review.status == "rejected":
                return ("rejected_source", None, ",".join(review.reasons[:8]))
            return ("verified", review, None)

        # Bounded adaptive search: no additional Tavily Search API requests.
        # max_pages is a total upper bound, not per-round.
        cursor = 0
        while cursor < page_budget:
            round_size = min(6 if rounds == 0 else 3, page_budget - cursor)
            candidates = ordered[cursor:cursor + round_size]
            cursor += len(candidates)
            rounds += 1
            selected_urls.update(canonical_url(c.url) for c in candidates)
            for c in candidates:
                audit = audit_by_url.get(canonical_url(c.url))
                if audit is not None:
                    audit["selected_for_extraction"] = True
                    audit["status"] = "extract_failed"

            sub_batch = search_result.model_copy(update={"candidates": candidates})
            extraction: ExtractionBatch = await self.extract(
                sub_batch, max_urls=len(candidates)
            )
            expected_urls = {canonical_url(c.url) for c in candidates}
            # Only process URLs actually selected in this round; prevents
            # unrelated provider results or faulty injected fixtures leaking in.
            pages = [
                p for p in extraction.pages
                if canonical_url(p.url) in expected_urls
            ]
            fetched_count += len(pages)
            outcomes = await asyncio.gather(*(extract_one(p) for p in pages))
            for page, (category, review, reason) in zip(pages, outcomes):
                row = audit_by_url.get(canonical_url(page.url))
                if row is not None:
                    row["status"] = category
                    row["reason"] = reason
                if category != "verified":
                    diagnostics[category] += 1
                    continue
                reviews.append(review)
                failures = check_eligibility(review, request)
                if failures:
                    diagnostics["hard_constraint_excluded"] += 1
                    if row is not None:
                        row["status"] = "hard_constraint_excluded"
                        row["reason"] = ",".join(failures[:3])
                else:
                    eligible.append(review)
            distinct = {
                " ".join((r.record.provider or "").casefold().split())
                for r in eligible if r.record.provider
            }
            if len(distinct) >= 6:
                break

        diagnostics["eligible_before_evaluation"] = len(eligible)
        diagnostics["discovery_rounds"] = rounds
        diagnostics["pages_attempted"] = len(selected_urls)
        assessments: list[FitAssessment] = []

        # Even if the verified sources are fewer than six, score them for an
        # explicitly labeled preliminary report. No roadmap until six.
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

        evaluations = await asyncio.gather(*(evaluate_one(r) for r in eligible))
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
            roadmap=roadmap, searched_pages=len(selected_urls),
            extracted_pages=fetched_count,
            reviewed_courses=len(reviews), diagnostics=diagnostics,
            candidate_audit=candidate_audit,
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
