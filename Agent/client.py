"""Minimal, bounded OpenRouter JSON client for the WAT agents."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"


class AgentCallError(RuntimeError):
    """A model call failed or returned invalid structured output."""


class OpenRouterClient:
    def __init__(self, *, api_key: str | None = None, model: str | None = None,
                 client: httpx.AsyncClient | None = None):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        self.model = model or os.getenv("OPENROUTER_MODEL")
        if not self.api_key or not self.model:
            raise AgentCallError("Set OPENROUTER_API_KEY and OPENROUTER_MODEL.")
        self.client = client

    async def complete(self, *, prompt_file: str, payload: dict[str, Any],
                       schema: type[BaseModel], retries: int = 1) -> BaseModel:
        """Return Pydantic-validated JSON. Does not mutate user inputs."""
        if not 0 <= retries <= 2:
            raise ValueError("retries must be between 0 and 2")
        root = Path(__file__).resolve().parents[1]
        prompt_path = (root / "Agent" / prompt_file).resolve()
        if prompt_path.parent != (root / "Agent").resolve() or not prompt_path.is_file():
            raise AgentCallError("Unknown agent prompt.")
        instructions = prompt_path.read_text(encoding="utf-8")
        own = self.client is None
        client = self.client or httpx.AsyncClient(timeout=55)
        try:
            for attempt in range(retries + 1):
                try:
                    response = await client.post(
                        ENDPOINT,
                        headers={"Authorization": f"Bearer {self.api_key}",
                                 "Content-Type": "application/json"},
                        json={
                            "model": self.model,
                            "temperature": 0,
                            "max_tokens": 2400,
                            "response_format": {"type": "json_object"},
                            "messages": [
                                {"role": "system", "content": instructions},
                                {"role": "user", "content": json.dumps(
                                    payload, ensure_ascii=False, default=str)},
                            ],
                        },
                    )
                    response.raise_for_status()
                    body = response.json()
                    content = body["choices"][0]["message"]["content"]
                    if not isinstance(content, str):
                        raise ValueError("Model returned non-text JSON payload.")
                    parsed = json.loads(content)
                    return schema.model_validate(parsed)
                except (httpx.HTTPError, ValueError, KeyError, IndexError,
                        TypeError, ValidationError) as exc:
                    if attempt == retries:
                        # Never include raw API response, supplied page text,
                        # user descriptions or credentials in the error message.
                        raise AgentCallError(
                            f"OpenRouter structured response failed after {attempt + 1} attempts "
                            f"({type(exc).__name__})."
                        ) from None
            raise AgentCallError("Model produced no valid output.")
        finally:
            if own:
                await client.aclose()
