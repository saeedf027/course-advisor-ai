# Adaptive Course Discovery and Preliminary Match Scores

## Goal
Avoid prematurely stopping after six weak search results. Search only once through Tavily, then inspect candidates in bounded rounds until six distinct eligible course providers are found or the explicit total-page budget is exhausted.

## Execution
- Retrieve Tavily Search results once, then rank and diversify all candidates.
- Round 1 extracts up to 6 URLs.
- Further rounds extract up to 3 unused URLs each, respecting the **total** `max_pages` cap (the manual live test defaults to 10 and allows 6/8/9/10/12).
- Stop early when 6 different providers pass source evidence verification and explicit hard-constraint checks.
- Limit concurrent model requests to 3, each to 30 seconds, with an outer 240-second pipeline timeout. More pages may cost additional Tavily and AvalAI credits.
- No hard constraint is relaxed, no provider is fabricated, and no repeated Tavily Search call is required.

## Early fit scoring
Any verified, hard-constraint-eligible courses are sent to the evaluation Agent even if fewer than six were found. The scorer uses the existing 35/25/25/15 rubric and soft preference adjustments. A partial result holds graded courses under `RankingResult.preview` and keeps `selected=[]`. The HTML labels these explicitly as **preliminary recommendations**, communicates insufficiency, and omits the final beginner roadmap. A complete report must still contain exactly six source-backed courses from six institutions.

## Diagnostics
`summary.json` includes:
- `status` (`ready` versus `insufficient_verified_courses`)
- `diagnostics.discovery_rounds`, `diagnostics.pages_attempted`
- `preliminary_scored_courses`, `preliminary_match_scores`
- `candidate_audit` with source title, URL and rejection status

These scores are *heuristic estimates of fit*, not empirically validated probabilities of learner success. Audit fields derive from public search pages, but sharing the report can reveal the user's learning request.

## Tests
Offline tests cover a second-round success, strict total-page budget, early partial scoring, and visually labeled incomplete reports. They do not prove live search coverage; a live run is still required.
