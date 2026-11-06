# Roadmap recovery after Live Test #9

The ninth live run reported `failed_stage=roadmap_validation`, `error_type=ValueError`, `eligible_before_evaluation=8`, `pages_attempted=9`, `discovery_rounds=2`, and zero source/relevance/evaluation failures. The original artifact does not contain the specific ValueError text or selected course URLs. Therefore it does not establish whether the model omitted a selected link or used an unselected URL.

## Recovery mechanism
- First use AvalAI to generate a curriculum-aware roadmap as before.
- Independently validate stage count/order, references, selected-course coverage, URLs and prerequisite/duration consistency.
- If the model call fails or the generated roadmap violates validation, *do not* fabricate courses, repeat the search, or throw away the completed six-source ranking.
- Fall back to three explicitly **advisory** stages with links only to the six already-verified selected course URLs (two alternatives per stage). These are generic study stages, not assertions that a particular course teaches undocumented content.
- A successful final report retains exactly six source-backed recommendations and an HTML visual roadmap, and the diagnostic counter `roadmap_fallback_used=1` signals that the model-authored roadmap was replaced.

The fallback does not replace source validation and does not claim a source-verified syllabus order. It does not assign undocumented course durations.

No live credits are spent during offline tests. A subsequent user-authorized smoke run is required to verify behavior with actual Tavily/AvalAI responses.
