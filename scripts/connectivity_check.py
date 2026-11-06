"""Small manual live test: one Tavily Search + one AvalAI chat request.

Prints only safe status summaries. Does not expose API keys or response body.
Requires explicit --confirm-live to spend credits.
"""
from __future__ import annotations

import argparse
import asyncio
import os

import httpx
from dotenv import load_dotenv

from Agent.client import AvalAIClient, AgentCallError
from Agent.needs_schema import LearningNeedsProfile

async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm-live", action="store_true")
    args = parser.parse_args()
    if not args.confirm_live:
        parser.error("Add --confirm-live to authorize a small paid API test.")
    load_dotenv()
    if not os.getenv("TAVILY_API_KEY") or not os.getenv("AVALAI_API_KEY"):
        print("MISSING_SECRET: TAVILY_API_KEY or AVALAI_API_KEY")
        return 2

    tavily_ok = False
    avalai_ok = False
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            r = await client.post(
                "https://api.tavily.com/search",
                headers={"Authorization": f"Bearer {os.environ['TAVILY_API_KEY']}"},
                json={"query": "data analysis beginner online course",
                      "search_depth": "basic", "max_results": 2,
                      "include_answer": False, "include_images": False},
            )
            r.raise_for_status()
            body = r.json()
            tavily_ok = isinstance(body.get("results"), list)
            print("TAVILY:", "PASS" if tavily_ok else "INVALID_RESPONSE")
        except (httpx.HTTPError, ValueError):
            print("TAVILY: REQUEST_FAILED")

        try:
            model = AvalAIClient(client=client)
            profile = await model.complete(
                prompt_file="needs_analysis.md",
                payload={"request": {"learning_request": {
                    "topic": "Data Analysis", "description": "I am a beginner.",
                    "level": "beginner"
                }, "preferences": {}, "constraints": {}, "settings": {
                    "hard_constraints": []}}},
                schema=LearningNeedsProfile, retries=0,
            )
            avalai_ok = profile.resolved_level == "beginner"
            print("AVALAI:", "PASS" if avalai_ok else "INVALID_RESPONSE")
        except (AgentCallError, ValueError):
            print("AVALAI: REQUEST_OR_SCHEMA_FAILED")
    return 0 if tavily_ok and avalai_ok else 1

if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
