"""No-network provider compatibility tests."""
import asyncio
import httpx
import pytest
from Agent.client import AvalAIClient, AgentCallError
from Agent.needs_schema import LearningNeedsProfile


def test_request_uses_avalai_endpoint_and_secret():
    calls = []
    def fake(request):
        calls.append(request)
        assert request.url == "https://api.avalai.ir/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer fake-key"
        data = {
            "topic": "Data Analysis", "resolved_level": "beginner",
            "level_source": "explicit", "level_confidence": "high",
            "learning_intent": "یادگیری مقدماتی تحلیل داده",
            "search_topics": ["Data Analysis", "Spreadsheets", "Charts"],
            "needs_learning_path": True, "hard_constraints": [],
        }
        return httpx.Response(200, json={
            "choices": [{"message": {"content": __import__("json").dumps(data)}}]
        })
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(fake)) as client:
            a = AvalAIClient(api_key="fake-key", client=client)
            return await a.complete(prompt_file="needs_analysis.md", payload={"topic": "Data Analysis"},
                                    schema=LearningNeedsProfile, retries=0)
    result = asyncio.run(run())
    assert result.needs_learning_path and len(calls) == 1


def test_missing_key_fails(monkeypatch):
    monkeypatch.delenv("AVALAI_API_KEY", raising=False)
    with pytest.raises(AgentCallError):
        AvalAIClient(api_key="")
