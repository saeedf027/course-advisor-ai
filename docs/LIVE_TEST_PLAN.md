# Live end-to-end acceptance plan (Step 09)

## Status as of 2026-11-06
- GitHub Actions PR #1 ran Python 3.12 offline tests: **45 passed**.
- **Live API test not run**: runtime has no TAVILY_API_KEY, OPENROUTER_API_KEY, OPENROUTER_MODEL.
- Do not confuse offline mock passing with verified course discovery.

## Two required cases
1. `tests/sample_input.json`: Persian beginner data analysis, free hard budget, 5 hours/week.
2. `tests/sample_input_ux.json`: English UX Design beginner, practical recorded preference, 6 hours/week.

## Execute locally, not in a public endpoint
Create a private `.env` from `.env.example`. Fill keys securely and choose an OpenRouter model compatible with JSON-object responses.

```bash
python -m pytest -q
python -m scripts.live_smoke --confirm-live
```

This consumes real credits: several search/extract requests and approximately one LLM call for every extracted course page and verified course, plus needs and roadmap calls. Inspect your provider usage dashboard first.

## Acceptance criteria
- No fabricated course cards or unverified URLs.
- Exactly 6 unique providers per ready report.
- Actual HTTPS course pages with evidence for name, provider, intended audience, syllabus topics, and level/duration.
- Hard constraints checked: free budget on data analysis; no unknown pricing accepted as free.
- Beginner visual roadmap displays 3–5 ordered stages and links only to the six selected course URLs.
- Two UTF-8 RTL HTML reports produced under `outputs/live/` with input summary.
- Failed search produces an honest insufficiency report; do not pretend it passed.

## Report results
`outputs/live/summary.json` contains status, counts and output filenames. Generated files are intentionally gitignored and should be reviewed for correctness and privacy before sharing with the teacher.

## Known blocking gaps
- Live API credentials/model selection.
- Current first-pass search coverage may fail to discover six distinct sourced courses; automatic query expansion is not yet implemented.
- Numeric budget, time, certificate and location strict filtering need richer course data.
- Required audience/syllabus evidence may be absent on some real provider pages.
- Prompt-injected course pages remain a risk; do not follow instructions in source text.
- Existing interactive HTML form prototype is not yet connected to the FastAPI endpoint.
- The current pipeline does not yet retry when six verified courses are unavailable.

## Review checklist
For each of the twelve intended suggestions: independently open the source URL, confirm the course is currently offered, compare titles and providers, inspect learning-level match, verify course duration and costs where mentioned, assess link accessibility and check that the Agent explanation actually follows evidence. Visual roadmap stages should be pedagogically logical and link to the correct real courses.
