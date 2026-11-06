"""Schema guidance and safe diagnostic tests, without external API requests."""
import asyncio
import json

import httpx
import pytest

from Agent.client import AvalAIClient, AgentCallError
from Agent.needs_schema import LearningNeedsProfile


def test_schema_is_included_in_agent_prompt():
    def handler(request):
        body = json.loads(request.content)
        system = body["messages"][0]["content"]
        assert "OUTPUT SCHEMA" in system
        assert "resolved_level" in system
        assert "search_topics" in system
        return httpx.Response(200, json={
            "choices": [{"message": {"content": json.dumps({
                "topic": "Data Analysis",
                "resolved_level": "beginner",
                "level_source": "explicit",
                "level_confidence": "high",
                "learning_intent": "یادگیری تحلیل داده برای مبتدیان",
                "search_topics": ["spreadsheets", "charts", "statistics"],
                "needs_learning_path": True
            })}}]
        })

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await AvalAIClient(api_key="fake-key", client=client).complete(
                prompt_file="needs_analysis.md", payload={"topic": "Data Analysis"},
                schema=LearningNeedsProfile, retries=0
            )
    assert asyncio.run(run()).resolved_level == "beginner"


def test_schema_mismatch_reports_only_field_and_type():
    def handler(request):
        return httpx.Response(200, json={
            "choices": [{"message": {"content": json.dumps({
                "topic": "Data Analysis", "resolved_level": "impossible-level",
                "secret": "DO_NOT_PRINT_THIS"
            })}}]
        })

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await AvalAIClient(api_key="fake-key", client=client).complete(
                prompt_file="needs_analysis.md", payload={"topic": "Data Analysis"},
                schema=LearningNeedsProfile, retries=0
            )
    with pytest.raises(AgentCallError) as exc:
        asyncio.run(run())
    assert "SCHEMA_MISMATCH" in str(exc.value)
    assert "resolved_level" in str(exc.value)
    assert "DO_NOT_PRINT_THIS" not in str(exc.value)
