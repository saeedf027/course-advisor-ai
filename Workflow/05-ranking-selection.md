# Step 05 — suitability assessment, hard filters and final selection

**State:** Deterministic filtering/scoring/selection code and offline tests added. LLM-generated assessments and end-to-end workflow remain unimplemented.

## Inputs
- `CourseAdvisorInput` and `LearningNeedsProfile` from Steps 01–02
- `CourseReview` objects from Step 04 (only status=verified is eligible)
- `FitAssessment` judgments for each course (later produced by LLM)

## Flow
1. Reject any review not marked source-backed `verified`.
2. Check each requested *hard* constraint deterministically. If an attribute is missing or cannot be compared, **exclude rather than guess**. Current support is limited to explicitly evidenced language and modality, free budget, and unrestricted budget; numeric capped budget and several constraints require richer structured data.
3. Match the grounded LLM assessment to the canonical course URL; missing assessment means exclude.
4. Calculate weighted 0–100 suitability score from four 0–5 judgments:
   - topic alignment: 35%
   - learner-level fit: 25%
   - learning-intent relevance: 25%
   - pedagogical fit: 15%
5. Deduplicate by provider + course title. Keep highest-scoring eligible record.
6. Sort by score, then deterministic provider/title/URL order.
7. Select at most one course per provider; require **exactly six distinct providers** to emit status `ready`. Otherwise emit `insufficient_verified_courses` and an *empty completed-result list*, so the UI cannot accidentally present fewer as a completed six-course report. Retain count and warning details for follow-up search.
8. Subsequent step generates the beginner roadmap only for a successful set when `needs_learning_path` is true.

## Why deterministic filtering?
An LLM may reason about relevance, but must never ignore budget restrictions, fabricate a missing fee or override a checked source record. A high match score cannot compensate for a hard-constraint mismatch.

## Caveat — scoring and quality
Scores express *relative model-assessed suitability*, not measured course outcomes. The default rubric should be evaluated on known examples and adjusted carefully (one variable at a time). No external course data or live LLM was called in this stage.

## Follow-on improvements
- Normalize cost into amount, currency, payment model; collect verified certificates, location and exact timetable/duration for hard constraints.
- Source freshness, contradictory provider details and semantic duplicate resolution.
- Add deterministic diversity of subjects/levels for beginner pathways while maintaining six distinct providers.
