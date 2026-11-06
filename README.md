# Course Advisor AI — مشاور دوره‌های آموزشی

پروژه تمرینی AI Players با معماری **Workflow–Agent–Tools (WAT)**، Python 3.12+، FastAPI، Tavily و AvalAI.

## Product behavior
- Learner supplies a topic and optional learning needs, constraints and preferences.
- Tavily discovers source pages; a grounded extraction Agent derives evidence-linked course data.
- Python filters and ranks course records and requires **six options from six distinct providers** for a completed report.
- Beginners additionally receive a structured 3–5-stage visual learning roadmap.
- The report is Persian RTL HTML, printable as PDF. When results are insufficient the system reports this clearly instead of fabricating courses.

## Runtime status
- **45 offline unit/integration tests passed** in GitHub Actions on 2026-11-06 before AvalAI migration; an additional offline AvalAI adapter test has now been committed.
- An end-to-end Python runner and FastAPI endpoint exist but **live API success remains to be tested**.
- The earlier HTML v1.2 form prototype is not yet connected to the backend.
- Several hard constraints need richer structured data; see `docs/LIVE_TEST_PLAN.md`.

## Source layout
```text
Workflow/runner.py          End-to-end Python orchestrator
Agent/client.py             AvalAI compatible chat/JSON adapter
Agent/                     Prompts and model contracts
Tools/                     Search, extract, validate, rank, roadmap, render
app/templates/report.html   RTL course cards + connected visual roadmap
app/main.py                 FastAPI /health and /report
tests/                      Offline tests and two example requests
scripts/connectivity_check.py   Small, explicit live connection test
scripts/live_smoke.py       Full live test for two topics; consumes more credits
.github/workflows/tests.yml             Automated offline pytest
.github/workflows/live-connectivity.yml Manual limited-credit live connectivity
```

## Test without API keys
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pytest -q
```

## Private configuration
Copy `.env.example` to `.env` locally, then set `TAVILY_API_KEY` and `AVALAI_API_KEY`. Optional: `AVALAI_MODEL=gpt-4o-mini` and `AVALAI_BASE_URL=https://api.avalai.ir/v1` (an alternative published domain is `https://api.avalai.org/v1`). **Never commit .env or any API keys.**

Repository secrets are only made available to explicitly configured GitHub Actions workflows.

## Small real API test (consumes credits)
Use GitHub Actions → **Live API connectivity (manual)** → **Run workflow** on main. This intentionally makes one Tavily search request and one AvalAI structured completion. Check its job summary for PASS/FAIL; it does *not* prove the full recommender works.

For local operation:
```powershell
python -m scripts.connectivity_check --confirm-live
```

## Full live evaluation (consumes more credits)
```powershell
python -m scripts.live_smoke --confirm-live
```
This tests `tests/sample_input.json` and `tests/sample_input_ux.json`. Review `outputs/live/summary.json`, generated HTML, source URL accuracy and estimated costs before presenting results.

## Reviewed documentation
- [Integration notes](Workflow/08-integration.md)
- [Live acceptance plan](docs/LIVE_TEST_PLAN.md)
- [Learning roadmap specification](Workflow/06-roadmap.md)

The approved Word PRD and separate v1.2 standalone UI prototype have not yet been committed here.
