# Step 07 — Persian RTL report rendering

**Status:** Jinja2 HTML renderer, responsive printable template and offline contract tests implemented. The full WAT execution engine is not wired yet.

## Role
Transform a Step 05 `RankingResult` and optional Step 06 `LearningRoadmap` into an HTML report; do not use an LLM to write HTML, invent courses, adjust scores or create links.

## Inputs
- Original validated `CourseAdvisorInput`
- `LearningNeedsProfile`
- `RankingResult` (ready exactly six, or insufficient with empty selection)
- Optional `LearningRoadmap` (beginners only, validated against the six selections)

## Validation
- Check original request against the needs profile and validate optional roadmap against the ranking.
- For ready reports require six courses from distinct providers, required fields, and HTTPS source URLs.
- For insufficient results render **no** course cards and no fabricated roadmap; show a clear insufficiency message.
- Use autoescaping for all input, LLM-authored or source-derived content. `href` links are canonicalized and restricted to HTTPS.
- A `demo=True` report is prominently labeled synthetic and is never a substitute for the assignment's real examples.

## Presentation
- Persian RTL, Vazirmatn/Vazir fallback.
- Six responsive cards: course title/provider, fit score, level/duration, audience, main topics, brief rationale, working source link.
- A distinct connected visual timeline of 3–5 stages for beginners, with learning objective, skills, prerequisites, estimated time (if available) and click-through links to selected courses.
- Mobile layout stacks cards and keeps the timeline vertical.
- Print CSS supports browser Save as PDF. Remote fonts require internet; fallback font remains available.

## Interface
`Tools.render.render_report(request, profile, ranking, roadmap=None, demo=False) -> str`
`Tools.render.save_report(html, destination) -> Path`

## Current constraints
- No live OpenRouter/Tavily pipeline yet: renderer consumes already validated in-memory models.
- Existing UI v1.2 remains a separate prototype; this is the result-report template that will later be integrated with its form.
- No server endpoint or PDF library is needed for the HTML MVP. Browser printing is sufficient for optional PDF.

## Security and content accuracy
Never render as factual recommendations if using fixtures. Keep `demo=True` for tests/examples, do not suppress the marker. HTML autoescape does not replace source verification, which remains the duty of previous steps.
