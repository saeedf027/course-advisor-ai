"""One-topic, opt-in real integration test with bounded source and LLM usage.

Reports accurate status, including insufficient coverage. Never logs credentials,
raw user descriptions or scraped page contents.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path

from dotenv import load_dotenv

from app.schemas import CourseAdvisorInput
from Workflow.runner import Pipeline
from Tools.render import save_report

ROOT = Path(__file__).resolve().parents[1]


async def main() -> int:
    parser = argparse.ArgumentParser(description="Real one-topic Course Advisor smoke test")
    parser.add_argument("--confirm-live", action="store_true", help="Authorize credit-consuming API requests")
    parser.add_argument("--max-pages", type=int, default=8, choices=range(1, 13), metavar="1..12")
    parser.add_argument("--input", default="tests/sample_input.json")
    parser.add_argument("--output-dir", default="outputs/smoke")
    args = parser.parse_args()
    if not args.confirm_live:
        parser.error("Live requests consume credits: supply --confirm-live")
    load_dotenv(ROOT / ".env")
    missing = [x for x in ("TAVILY_API_KEY", "AVALAI_API_KEY") if not os.getenv(x)]
    if missing:
        print("Missing secret names: " + ", ".join(missing))
        return 2

    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    result_info = {"topic_id": "data_analysis",
                   "disclaimer": "Live API smoke test; source quality requires manual review."}
    try:
        request = CourseAdvisorInput.model_validate_json(
            Path(args.input).read_text(encoding="utf-8")
        )
        result = await asyncio.wait_for(\n            Pipeline(max_pages=args.max_pages, llm_concurrency=3,\n                     agent_timeout_seconds=30).run(request),\n            timeout=240,\n        )
        report = save_report(result.report_html, output / "report.html")
        result_info.update(
            status=result.status, candidate_pages=result.searched_pages,
            extracted_pages=result.extracted_pages,
            structurally_verified_courses=result.reviewed_courses,
            selected_courses=len(result.ranking.selected),
            roadmap_steps=len(result.roadmap.steps) if result.roadmap else 0,
            report_file=report.name,
            diagnostics=result.diagnostics or {},
        )
        # Insufficient results is an expected report state, not a CI technical failure.
        code = 0
    except Exception as exc:
        # Only type names go in GitHub Actions logs/artifact; no secrets or page data.
        result_info.update(status="technical_error", error_type=type(exc).__name__)
        code = 1
    (output / "summary.json").write_text(
        json.dumps(result_info, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(result_info, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
