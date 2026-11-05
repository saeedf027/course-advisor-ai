# Step 08 — Integrate and run the WAT pipeline

## Files
- `Agent/client.py`: OpenRouter chat-completions adapter requesting JSON object responses and validating Pydantic model outputs.
- `Agent/extraction_schema.py`: separate actual course page vs non-course page.
- `Workflow/runner.py`: Python step orchestrator and CLI.
- `app/main.py`: minimal FastAPI API (`/health`, `POST /report`).
- `tests/test_workflow.py`: isolated mock end-to-end coverage.

## End-to-end path
`CourseAdvisorInput → needs agent → search planner → Tavily Search → Tavily Extract → course extraction agent → deterministic source review → evaluation agent → deterministic 6-provider selection → beginner roadmap agent (if applicable) → validated Jinja2 HTML report`.

## Setup (Python 3.12+)
```bash
python -m venv .venv
# Windows PowerShell:
.venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
cp .env.example .env  # On PowerShell: Copy-Item .env.example .env
# Fill OPENROUTER_API_KEY, OPENROUTER_MODEL, TAVILY_API_KEY locally.
python -m pytest -q
python -m Workflow.runner --input tests/sample_input.json --output outputs/report.html
# optional local-only API:
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
Never commit `.env`. API credits are consumed by live runs.

## Current guarantees
- Constrained first search pass, max 20 pages extracted in groups.
- LLM calls have bounded retry (1 retry by default) and Pydantic validation.
- A page or judgment that fails agent JSON parsing is skipped.
- Only source-backed records survive the deterministic review gate.
- The 6-course condition is checked before rendering. No fabricated fill.
- Beginner roadmaps must reference all 6 chosen URLs.
- The generated HTML can be printed as a PDF with the browser.

## MVP limitations and priorities
1. **Not yet live-tested:** no API credentials available to this execution environment. OpenRouter model compatibility with `response_format=json_object` should be tested with the chosen model.
2. **Search coverage:** adaptive queries and multiple passes are not implemented; one pass can return insufficient results (especially with restrictive filters).
3. **Hard constraint coverage:** numerical budgets, certificate, schedule and geographic constraints need structured facts and evidence; these are fail-closed.
4. **Security:** the FastAPI endpoint lacks auth and rate limiting; use only locally until guarded. User page text is passed to LLM as data with strict instructions, but prompt injection risks remain.
5. **Source factuality:** literal quote matching is a basic evidence check, not independent verification or semantic fact correctness. Some course pages lack audience/syllabus information and are rejected by design.
6. **Privacy:** descriptions can contain personal data. Avoid sensitive input; requests are sent to external OpenRouter/Tavily services.
7. **UI:** separate user form prototype v1.2 has not been integrated with the API; current runnable report path accepts a JSON file or POST body.
8. **Evaluation:** add real-course evaluations and two verified reports for two different topics after configuring APIs.

## Next step
Run all offline tests, then supply local keys, run two live topics, inspect source accuracy, fix integration issues and complete deliverables.
