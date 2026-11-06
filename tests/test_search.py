"""Offline tests of query planning, source normalization and Tavily adapter."""
import asyncio
import httpx

from app.schemas import CourseAdvisorInput
from Agent.needs_schema import LearningNeedsProfile
from Tools.search import (build_search_plan, canonical_url, merge_results,
                          run_search, CandidatePage, prioritize_candidates, candidate_priority)


def request_and_profile():
    request = CourseAdvisorInput.model_validate({
        "learning_request": {"topic": "تحلیل داده", "level": "beginner"},
        "preferences": {"language": "fa", "format": "recorded_online"},
        "constraints": {"budget": {"mode": "free"}},
        "settings": {"hard_constraints": ["budget"]},
    })
    profile = LearningNeedsProfile.model_validate({
        "topic": "تحلیل داده", "resolved_level": "beginner",
        "level_source": "explicit", "level_confidence": "high",
        "learning_intent": "شروع تحلیل داده از صفر",
        "search_topics": ["مبانی تحلیل داده", "تحلیل داده با اکسل", "مصورسازی داده‌ها"],
        "suggested_prerequisites": [],
        "hard_constraints": ["budget"], "needs_learning_path": True, "notes": [],
    })
    return request, profile


def test_search_plan_has_broad_specialized_and_preference():
    request, profile = request_and_profile()
    plan = build_search_plan(request, profile, max_queries=5)
    kinds = {item.kind for item in plan.queries}
    assert kinds == {"broad", "specialized", "preference"}
    assert any("رایگان" in item.query for item in plan.queries)
    assert len(plan.queries) <= 5
    assert all(len(item.query) <= 400 for item in plan.queries)


def test_minimal_search_plan():
    request, profile = request_and_profile()
    request = CourseAdvisorInput.model_validate({"learning_request": {"topic": "Design Systems"}})
    profile = profile.model_copy(update={
        "topic": "Design Systems", "resolved_level": "unknown", "level_source": "unknown",
        "needs_learning_path": False, "hard_constraints": [],
        "search_topics": ["UI Design"],
    })
    assert build_search_plan(request, profile).queries


def test_duplicate_url_tracking_is_removed():
    result = merge_results([
        ("A", [{"url": "https://example.com/course?utm_source=x", "title": "A"}]),
        ("B", [{"url": "https://example.com/course/", "title": "B"}]),
    ])
    assert len(result.candidates) == 1
    assert result.candidates[0].source_queries == ["A", "B"]
    assert result.candidates[0].verified_course is False


def test_localhost_url_is_rejected():
    assert canonical_url("http://localhost:8000/test") is None
    assert canonical_url("javascript:alert(1)") is None


def test_tavily_adapter_with_mock_transport():
    seen = []
    def handler(req):
        assert req.url == "https://api.tavily.com/search"
        seen.append(req)
        return httpx.Response(200, json={"results": [
            {"url": "https://example.org/course", "title": "Mock course page",
             "content": "Unverified result", "score": 0.8}
        ]})
    async def execute():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            request, profile = request_and_profile()
            return await run_search(build_search_plan(request, profile, max_queries=2),
                                    api_key="test-key", client=client)
    result = asyncio.run(execute())
    assert len(seen) == 2
    assert len(result.candidates) == 1
    assert result.total_results_before_dedup == 2
    assert not result.errors

def test_course_likelihood_ranks_detail_before_blog_article():
    pages = [
        CandidatePage(url="https://example.edu/blog/best-courses", title="Best courses in data", snippet=""),
        CandidatePage(url="https://academy.example.edu/courses/data-analysis-101",
                      title="Data Analysis Course – Curriculum", snippet=""),
    ]
    assert candidate_priority(pages[1]) > candidate_priority(pages[0])
    assert prioritize_candidates(pages, limit=1)[0].url == pages[1].url


def test_course_candidates_diversify_hosts_in_small_budget():
    pages = [
        CandidatePage(url="https://school-a.example/courses/one", title="Course One", snippet=""),
        CandidatePage(url="https://school-a.example/courses/two", title="Course Two", snippet=""),
        CandidatePage(url="https://school-b.example/courses/three", title="Course Three", snippet=""),
    ]
    chosen = prioritize_candidates(pages, limit=2)
    assert len(chosen) == 2
    from urllib.parse import urlsplit
    assert len({urlsplit(c.url).hostname for c in chosen}) == 2
