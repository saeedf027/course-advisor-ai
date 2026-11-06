# WAT runtime limits and cost controls

The current Course Advisor AI implementation was optimized following an excessively long 12-page live test.

## Live execution budget
- Default manual test: 6 pages (users may explicitly choose 8, 10 or 12).
- Entire pipeline: 240-second timeout. A timeout is reported as a technical error in the JSON artifact.
- GitHub Actions job: 7-minute limit including dependency installation.
- One LLM attempt per stage (no automatic re-query) with a 30-second cap per call.
- Maximum of three simultaneous AvalAI requests, enforced by a semaphore (up to four configurable for local use).
- Tavily query execution is concurrent, also bounded at three.
- When fewer than six **distinct verified and hard-constraint-eligible providers** exist, scoring LLM calls are entirely skipped.
- Failed or insufficient runs never fabricate courses. Insufficient source-backed results are recorded as a valid diagnostic outcome, *not* a completed six-course report.

## Quality and security considerations
A faster workflow does not guarantee six real courses. A limited source budget may produce an honest insufficiency result. Extracted pages still require matched evidence and hard constraints remain strict. GitHub artifacts contain user-provided form data in the report: review before sharing publicly. No API keys are stored or logged.

## Diagnostics
`outputs/smoke/summary.json` includes structural counts for agent extraction errors, non-course pages, incomplete/rejected sources, hard-constraint exclusions, skipped evaluations and failed assessments. Raw source text and secret values are not included.

## Verification
Offline pytest covers completion and insufficient-source branches, concurrency limits and evaluation early exit. These tests do **not** prove performance with live provider latency. Re-run the manual smoke test only when you authorize its credit consumption.
