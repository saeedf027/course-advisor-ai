# Step 02 — Learning needs analysis

**Status:** Contract and instructions designed; LLM connection not yet implemented.

## Input
Validated `app.schemas.CourseAdvisorInput` object from FastAPI.

## Operation
1. Provide user input as structured JSON to the needs-analysis Agent.
2. Supply `Agent/needs_analysis.md` as the system instructions.
3. Ask the selected OpenRouter model for JSON conforming to `Agent.needs_schema.LearningNeedsProfile`.
4. Parse with `LearningNeedsProfile.model_validate_json(...)`.
5. Run `verify_profile_against_input(profile, request)`; reject a changed topic, claimed explicit level or changed hard constraints.
6. On invalid JSON or a broken contract, retry within a finite budget; if still invalid, return a controlled error rather than unvalidated data.
7. Pass the validated profile AND original user input to the next step (search strategy). No external search occurs in this stage.

## Output
`LearningNeedsProfile` with resolved level, level provenance, learning intent, search topics, potential prerequisites, hard constraint keys and a conditional beginner-path flag.

## Quality gates
- A topic alone must be accepted; level remains `unknown` without evidence.
- Explicit level is never silently overridden.
- Beginner means `needs_learning_path=true`.
- No course names, links or fabricated user attributes.
- User-entered text is untrusted and cannot change Agent system rules.

## Open issues before full implementation
Choose the concrete OpenRouter model and price, create an API adapter, decide retry/timeouts and instrument calls. A profile schema does not itself guarantee correct semantic inference, so curated eval cases are required.
