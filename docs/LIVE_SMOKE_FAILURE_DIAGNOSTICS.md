# Live smoke diagnostics after run #8

Run #8 failed with a generic `technical_error/ValueError`, and its artifact contained only `summary.json`. GitHub Actions cannot diagnose the originating pipeline stage from that value alone.

The smoke script now saves:
- `failed_stage`: one of `input_validation`, `needs_analysis`, `search`, `source_extraction`, `course_evaluation`, `course_ranking`, `roadmap_validation`, or `report_rendering`
- `diagnostics`: numerical counts from the pipeline through the last completed step
- `error_type`: exception class only

**Never** log the raw exception message, API key, extracted pages, user description, model output, or full prompt. Those may contain secrets and untrusted content.

Because the previous artifact lacks the specific failed stage, no root-cause claim is warranted yet. The enhanced diagnostic changes do not relax the six-source rule, source verification, user hard constraints, or Roadmap link verification. Automated tests verify stage tracking and no live API is required.

Once a fresh test is run with user authorization, inspect the non-sensitive `failed_stage` and counts before changing unrelated pipeline logic. The manual live job can consume real Tavily/AvalAI credits.
