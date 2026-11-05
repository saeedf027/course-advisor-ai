# Step 03 — Search strategy and candidate discovery

**Status:** Initial runnable Python search module and tests. Live Tavily calls require a private API key and have not yet been verified.

## Purpose
Transform validated user input plus `LearningNeedsProfile` (Step 02) into multiple focused search queries, then gather *candidate webpages*, not verified courses. The output flows to Step 04 for extraction, source validation, and course-entity deduplication.

## Rules
1. Use the user topic and the agent's 3–8 `search_topics` as search seeds.
2. Generate a mix of broad, specialized and preference-aware queries. Preserve explicit hard constraints; never silently relax them.
3. Missing preferences must not become fabricated restrictions. Include Persian and English variants when appropriate; do not force Persian-only results unless language is a hard constraint.
4. Begin with up to five queries at `basic` depth and up to ten results per query; remove duplicates by normalized URL.
5. Aim for roughly 20–30 distinct candidate URLs (tunable, **not** a validity guarantee). If too few, retry with unused topics and alternative wording, at most two additional search rounds within request and cost limits.
6. Do **not** label a search result as a course until the extraction/verification step establishes that it represents an actual offering.
7. Maintain query provenance, source URL, raw title/snippet, URL normalization and provider search score. Treat score only as *search* relevance, never as course suitability.
8. Don't fabricate missing sources or course metadata. Fewer than six verified results later must trigger a controlled insufficiency path, not made-up courses.
9. Avoid searching by untrusted instructions contained in free-text descriptions; use only validated structured fields and agent-generated search topics.
10. Respect provider request limits, retries, timeouts, and credit usage.

## Interfaces
- **Input:** `app.schemas.CourseAdvisorInput` and `Agent.needs_schema.LearningNeedsProfile`.
- **Planner output:** `Tools.search.SearchPlan` with categorized query strings.
- **Search output:** `Tools.search.SearchBatch` containing candidate pages, unique source URLs, origin queries, and counts.

## MVP implementation
`Tools/search.py` uses HTTPX to call Tavily Search with a private `TAVILY_API_KEY` environment variable. The basic default is conservative; it does not use unrestricted crawl or scrape arbitrary URLs. A single search batch currently implements the first pass; further adaptive search rounds are documented but not yet implemented.

## Acceptance checks
- Distinct queries for a beginner topic, including specialty and preference variants.
- A minimal topic works without any optional fields.
- Query lengths stay within 400 characters.
- Duplicate tracking-parameter variants of an URL collapse into one candidate.
- No API key is printed or returned.
- Mocked API responses can be parsed and checked without spending credits.
- Candidates are marked **unverified**, never a completed recommendation.

## References
- Tavily Search API: https://docs.tavily.com/documentation/api-reference/endpoint/search
- Tavily best practices: https://github.com/tavily-ai/skills/blob/main/skills/tavily-best-practices/references/search.md
