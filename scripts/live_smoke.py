"""Explicit opt-in live E2E smoke test for two distinct learner topics.

Uses real Tavily and AvalAI calls. Do not run without an approved credit
budget and valid private .env credentials. Output files are gitignored.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from app.schemas import CourseAdvisorInput
from Workflow.runner import Pipeline
from Tools.render import save_report

ROOT = Path(__file__).resolve().parents[1]
TOPICS = (
    ("data_analysis", ROOT / "tests" / "sample_input.json"),
    ("ux_design", ROOT / "tests" / "sample_input_ux.json"),
)


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm-live", action="store_true",
                        help="Explicitly authorize API calls that can consume credits.")
    parser.add_argument("--output-dir", default="outputs/live")
    args = parser.parse_args()
    if not args.confirm_live:
        parser.error("Live calls spend API credits: pass --confirm-live explicitly.")
    load_dotenv(ROOT / ".env")
    missing = [name for name in ("TAVILY_API_KEY", "AVALAI_API_KEY")
               if not os.getenv(name)]
    if missing:
        print("Missing configuration: " + ", ".join(missing), file=sys.stderr)
        return 2
    destination = Path(args.output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    summary = []
    for label, path in TOPICS:
        request = CourseAdvisorInput.model_validate_json(path.read_text(encoding="utf-8"))
        try:
            result = await Pipeline(max_pages=20).run(request)
            output = save_report(result.report_html, destination / f"{label}.html")
            summary.append({
                "topic": label, "status": result.status,
                "selected_count": len(result.ranking.selected),
                "candidate_pages": result.searched_pages,
                "extracted_pages": result.extracted_pages,
                "reviewed_courses": result.reviewed_courses,
                "roadmap_steps": len(result.roadmap.steps) if result.roadmap else 0,
                "html_file": str(output),
            })
        except Exception as exc:
            # No raw page text, tokens, or personal descriptions in the logs.
            summary.append({"topic": label, "status": "error",
                            "error_type": type(exc).__name__})
    summary_path = destination / "summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if all(x["status"] == "ready" for x in summary) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
