# Step 06 — Beginner Learning Roadmap

**Status:** Structured data model, validation function and offline tests implemented. LLM invocation and visual rendering are still pending.

## Purpose
After six valid courses are ranked, optionally create a stepwise learning path for beginners. The result is a **structured JSON object**, not an image.

## Inputs
- Validated `CourseAdvisorInput`
- `LearningNeedsProfile` from Step 02
- `RankingResult` from Step 05

## Branches
- Non-beginner (`needs_learning_path=false`) → output `null`, proceed directly to report.
- Beginner with `ranking.status != ready` → `null`, report insufficient options or rerun search; do not fabricate a roadmap.
- Beginner with exactly six selected courses → invoke a roadmap-generating LLM with `Agent/roadmap_generation.md`, validate JSON and selected-course references via `Tools.roadmap.validate_roadmap`.

## Output schema
`LearningRoadmap`:
- `title`, `summary`, `audience_level`, `duration_disclaimer`
- `steps`: 3–5 `RoadmapStep` records
  - consecutive `step_number`
  - `title`, `goal`, `skills`, `prerequisites`
  - `recommended_course_urls` referring ONLY to Step 05's selected six
  - optional `estimated_weeks_min/max` and `estimated_time_note`

## Acceptance rules
1. 3–5 consecutively numbered stages.
2. Every stage links to >=1 of the six selected courses.
3. Across all stages, all six selected courses are visible (as choices, not mandatory purchases).
4. No unknown links, duplicate links within a stage or fabricated sources.
5. For non-beginners or incomplete selections, no roadmap is created.
6. Durations clearly marked as estimates; never treat them as exact provider claims.

## Visualization contract for Step 07
- Desktop: responsive, connected roadmap; horizontal or vertical timeline according to available width.
- Mobile/PDF: stacked vertical timeline that preserves order, goals and associated courses.
- Each stage card: number, title, goal, skills, optional prerequisite, estimated time if available, and clickable course titles mapped via URL to the selected course records.
- User can distinguish **alternative courses** within a stage from mandatory sequential steps.
- Text is Persian RTL, font Vazir/Vazirmatn; avoid a raster image so content remains selectable, accessible and printable.
- Links must be safe HTTPS URLs and escaped during HTML generation.
- If `roadmap=null`, omit section rather than showing fictitious placeholders.

## Remaining work
Implement OpenRouter LLM call, semantic evaluation of stage logic, retry handling, and Step 07 HTML renderer. A validated structure does not ensure pedagogical soundness: evaluate real examples.
