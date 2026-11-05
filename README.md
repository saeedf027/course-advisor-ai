# Course Advisor AI

مشاور هوشمند انتخاب دوره آموزشی — تمرین AI Players با معماری **WAT (Workflow / Agent / Tools)**.

## Product
Users provide a learning topic and, optionally, description, current proficiency, course format/language, budget, schedule and learning preferences. The system will find and verify real courses, explain the suitability of **six** options with source links, and additionally produce an ordered learning roadmap when the user is a beginner.

**Current phase:** Python input-contract baseline and project structure. The search/LLM workflow has **not** been implemented. The six-course mock data in the UI prototype is **not** verified and must not be presented as real results.

## Stack
Python 3.12+, FastAPI, Pydantic v2, HTML/CSS/JavaScript, Jinja2, Tavily Search/Extract, OpenRouter LLM, HTTPX and pytest.

## Repository map
```text
Workflow/               Workflow design and future Python runner
Agent/                  Agent instructions and future prompts
Tools/                  Planned search/extract/validate/render modules
app/schemas.py          Validated API input contract
tests/sample_input.json Example learner profile
tests/test_schemas.py   Input-contract checks
docs/PROJECT_SPEC.md    Approved PRD and tech-stack summary
docs/UI_HANDOFF.md      Approved UI design status and integration notes
outputs/                Generated reports (gitignored)
.env.example            Required secrets names, no real secrets
```

## Run the currently available tests
```bash
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m pytest -q
```

No API keys are required for these schema tests. To configure future integrations, copy `.env.example` to `.env` and keep it private. Never commit credentials to this public repo.

## Next phase
Design the educational-needs analysis Agent, define its output JSON contract, then implement the WAT pipeline iteratively. See [Workflow](Workflow/README.md), [Agent](Agent/README.md), and [Tools](Tools/README.md).

## Note for reviewers
Implementation milestones are recorded in Git history. The full approved Word PRD and HTML UI v1.2 are available separately and are not yet in this GitHub repository.
