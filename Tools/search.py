"""Tavily-backed discovery of *unverified source pages* for Course Advisor AI.

Step 03 only. Never treat a result as a verified course until the next stages.
"""
from __future__ import annotations

import asyncio
import os
import re
from typing import Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx
from pydantic import Field

from app.schemas import CourseAdvisorInput, StrictModel
from Agent.needs_schema import LearningNeedsProfile, verify_profile_against_input

SEARCH_ENDPOINT = "https://api.tavily.com/search"
TRACKING_PARAMS = {"fbclid", "gclid", "yclid", "mc_cid", "mc_eid"}


class SearchQuery(StrictModel):
    query: str = Field(min_length=4, max_length=400)
    kind: Literal["broad", "specialized", "preference"]


class SearchPlan(StrictModel):
    queries: list[SearchQuery] = Field(min_length=1, max_length=8)


class CandidatePage(StrictModel):
    url: str
    title: str
    snippet: str
    source_queries: list[str] = Field(default_factory=list)
    provider_search_score: float | None = None
    verified_course: Literal[False] = False


class SearchBatch(StrictModel):
    candidates: list[CandidatePage]
    searched_queries: list[str]
    total_results_before_dedup: int
    errors: list[str] = Field(default_factory=list)


def canonical_url(value: str) -> str | None:
    """Normalize safe HTTP(S) results and remove common tracking parameters."""
    try:
        p = urlsplit(value.strip())
    except (ValueError, TypeError, AttributeError):
        return None
    if p.scheme.lower() not in {"http", "https"} or not p.hostname:
        return None
    if p.username or p.password:
        return None
    host = p.hostname.lower()
    if host in {"localhost"} or host.endswith(".local"):
        return None
    try:
        port = p.port
    except ValueError:
        return None
    host_display = f"[{host}]" if ":" in host else host
    if port and not ((p.scheme == "https" and port == 443) or (p.scheme == "http" and port == 80)):
        host_display += f":{port}"
    kept = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
            if not k.lower().startswith("utm_") and k.lower() not in TRACKING_PARAMS]
    path = p.path.rstrip("/") or "/"
    return urlunsplit((p.scheme.lower(), host_display, path, urlencode(kept), ""))


def build_search_plan(request: CourseAdvisorInput, profile: LearningNeedsProfile,
                      max_queries: int = 5) -> SearchPlan:
    """Build a transparent, deterministic first-pass query mix."""
    verify_profile_against_input(profile, request)
    if not 1 <= max_queries <= 8:
        raise ValueError("max_queries must be between 1 and 8")
    base = request.learning_request.topic
    level = "beginner " if profile.resolved_level == "beginner" else ""
    seeds = [base] + [x for x in profile.search_topics if x.strip().casefold() != base.casefold()]
    proposed: list[SearchQuery] = []

    def add(query: str, kind: Literal["broad", "specialized", "preference"]) -> None:
        query = re.sub(r"\s+", " ", query).strip()[:400].strip()
        if len(query) >= 4 and not any(x.query.casefold() == query.casefold() for x in proposed):
            proposed.append(SearchQuery(query=query, kind=kind))

    add(f"دوره آموزشی {base} {'مقدماتی ' if level else ''}سرفصل مخاطبان ثبت نام", "broad")
    add(f"{base} {'beginner ' if level else ''}course curriculum enrollment", "broad")
    for seed in seeds[1:4]:
        add(f"دوره {seed} سرفصل آموزش {'مبتدی' if level else ''}", "specialized")

    pref_parts = []
    if request.preferences.language:
        pref_parts.append("فارسی" if request.preferences.language == "fa" else request.preferences.language)
    if request.constraints.budget.mode == "free":
        pref_parts.append("رایگان")
    if request.preferences.format == "recorded_online":
        pref_parts.append("ضبط شده آنلاین")
    elif request.preferences.format == "live_online":
        pref_parts.append("آنلاین زنده")
    elif request.preferences.format == "in_person" and request.constraints.location:
        pref_parts.append("حضوری " + request.constraints.location)
    if pref_parts:
        add(f"دوره {base} {' '.join(pref_parts)}", "preference")
    # Preserve a preference-specific query even when specialized seeds are numerous.
    prioritized = [q for q in proposed if q.kind == "broad"]
    prioritized += [q for q in proposed if q.kind == "preference"]
    prioritized += [q for q in proposed if q.kind == "specialized"]
    return SearchPlan(queries=prioritized[:max_queries])


# Search-result prioritization is only a retrieval heuristic, NOT factual verification.
# URL shape is more useful than a generic "course" keyword in a site homepage.
DETAIL_SEGMENTS = {"course", "courses", "lesson", "lessons", "product",
                   "class", "classes", "module", "modules", "academies"}
CATALOG_SEGMENTS = {"browse", "category", "categories", "search", "tag",
                    "tags", "catalog", "subjects", "subject", "how-to-learn"}
ARTICLE_SEGMENTS = {"blog", "article", "articles", "news", "forum",
                    "forums", "questions", "resources", "roadmap"}
OTHER_RESOURCE_DOMAINS = {"youtube.com", "youtu.be", "aparat.com",
                          "reddit.com", "medium.com", "wikipedia.org"}
COURSE_TITLE_SIGNALS = ("دوره", "کلاس", "آموزش", "course", "class", "training",
                        "certificate", "module")
LIST_TITLE_SIGNALS = ("بهترین دوره", "فهرست دوره", "لیست دوره",
                      "مجموعه‌های آموزشی", "آموزشگاه", "نقشه راه",
                      "best courses", "top courses", "learning path",
                      "courses |", "courses -", "دوره‌های آموزشی")


def candidate_priority(page: CandidatePage, topic: str | None = None) -> int:
    """Explainable ranking of likely *individual* course pages.

    This does not certify provider identity or claim that a course is valid.
    Search snippets and titles are untrusted and only control fetch priority.
    """
    parsed = urlsplit(page.url)
    host = (parsed.hostname or "").lower()
    parts = [p.casefold() for p in parsed.path.split("/") if p]
    text = (page.title + " " + page.snippet[:350]).casefold()
    title = page.title.casefold()
    score = 2 * min(len(page.source_queries), 3)
    if any(host == bad or host.endswith("." + bad)
           for bad in OTHER_RESOURCE_DOMAINS):
        score -= 16
    if parsed.path.lower().endswith((".pdf", ".mp4", ".docx")):
        score -= 20
    if not parts:  # A homepage, even when titled "Data Analysis Academy".
        score -= 18
    if any(p in ARTICLE_SEGMENTS for p in parts):
        score -= 20
    if any(p in CATALOG_SEGMENTS for p in parts):
        score -= 18
    if any(p in DETAIL_SEGMENTS and i + 1 < len(parts)
           for i, p in enumerate(parts)):
        score += 15
    elif len(parts) >= 2 and any(p in DETAIL_SEGMENTS for p in parts):
        score += 5
    if any(signal in title for signal in COURSE_TITLE_SIGNALS):
        score += 4
    if any(signal in title for signal in LIST_TITLE_SIGNALS):
        score -= 10
    if any(p in {"watch", "video", "videos"} for p in parts):
        score -= 12
    if topic:
        normalized_topic = " ".join(topic.casefold().split())
        if normalized_topic in text:
            score += 6
        else:
            tokens = [t for t in normalized_topic.split() if len(t) >= 3]
            if tokens and all(t in text for t in tokens):
                score += 3
    # Tavily score is relevance to *query*, not course suitability.
    if page.provider_search_score is not None:
        score += round(min(1.0, max(0.0, page.provider_search_score)) * 2)
    return score


def prioritize_candidates(
    candidates: list[CandidatePage], limit: int, topic: str | None = None
) -> list[CandidatePage]:
    """Prefer topic-relevant course details, then diversify site hosts."""
    if limit < 1:
        raise ValueError("limit must be positive")
    ordered = sorted(candidates, key=lambda p: (
        -candidate_priority(p, topic),
        p.url,
    ))
    selected: list[CandidatePage] = []
    seen_hosts: set[str] = set()
    for p in ordered:
        hostname = urlsplit(p.url).hostname or ""
        if hostname not in seen_hosts:
            selected.append(p)
            seen_hosts.add(hostname)
            if len(selected) == limit:
                return selected
    for p in ordered:
        if p not in selected:
            selected.append(p)
            if len(selected) == limit:
                break
    return selected


def merge_results(query_results: list[tuple[str, list[dict]]], errors: list[str] | None = None) -> SearchBatch:
    """Collapse URL duplicates; preserve which queries found each source."""
    by_url: dict[str, CandidatePage] = {}
    count = 0
    for query, results in query_results:
        for item in results:
            if not isinstance(item, dict):
                continue
            count += 1
            url = canonical_url(item.get("url", ""))
            if not url:
                continue
            if url not in by_url:
                raw_score = item.get("score")
                score = float(raw_score) if isinstance(raw_score, (int, float)) and not isinstance(raw_score, bool) else None
                by_url[url] = CandidatePage(
                    url=url, title=str(item.get("title") or "")[:500],
                    snippet=str(item.get("content") or "")[:4000],
                    source_queries=[query], provider_search_score=score,
                )
            elif query not in by_url[url].source_queries:
                by_url[url].source_queries.append(query)
    return SearchBatch(
        candidates=list(by_url.values()),
        searched_queries=[query for query, _ in query_results],
        total_results_before_dedup=count,
        errors=errors or [],
    )


async def run_search(
    plan: SearchPlan, api_key: str | None = None,
    client: httpx.AsyncClient | None = None,
    max_results_per_query: int = 10,
    concurrency: int = 3,
) -> SearchBatch:
    """Concurrent but bounded first-pass Tavily search.

    API responses are stored in query order for stable provenance. No results
    are invented if one of the independent searches fails.
    """
    key = api_key or os.getenv("TAVILY_API_KEY")
    if not key:
        raise RuntimeError("TAVILY_API_KEY is missing; set it in your local environment.")
    if not 1 <= max_results_per_query <= 20:
        raise ValueError("max_results_per_query must be in 1..20")
    if not 1 <= concurrency <= 4:
        raise ValueError("concurrency must be in 1..4")
    own_client = client is None
    if own_client:
        client = httpx.AsyncClient(timeout=20)
    gate = asyncio.Semaphore(concurrency)

    async def search_one(index: int, entry: SearchQuery):
        async with gate:
            try:
                response = await client.post(
                    SEARCH_ENDPOINT,
                    json={
                        "query": entry.query, "topic": "general",
                        "search_depth": "basic", "max_results": max_results_per_query,
                        "include_answer": False, "include_raw_content": False,
                        "include_images": False,
                    },
                    headers={
                        "Authorization": f"Bearer {key}",
                        "Content-Type": "application/json",
                    },
                )
                response.raise_for_status()
                body = response.json()
                if not isinstance(body, dict) or not isinstance(body.get("results"), list):
                    raise ValueError("Invalid Tavily response structure")
                return (entry.query, body["results"], None)
            except (httpx.HTTPError, ValueError) as exc:
                return (entry.query, [], f"Search query #{index + 1} failed: {type(exc).__name__}")

    try:
        results = await asyncio.gather(
            *(search_one(i, entry) for i, entry in enumerate(plan.queries))
        )
        query_results = [(query, items) for query, items, _ in results]
        errors = [error for _, _, error in results if error is not None]
        return merge_results(query_results, errors)
    finally:
        if own_client:
            await client.aclose()
