"""Bounded, OpenAI-compatible JSON completion client using AvalAI.

No credentials are stored in source code. Tests may inject httpx.AsyncClient.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

DEFAULT_BASE_URL = "https://api.avalai.ir/v1"


class AgentCallError(RuntimeError):
    """Model request failed; safe for public CI logs."""


class AvalAIClient:
    def __init__(self, *, api_key: str | None = None, model: str | None = None,
                 base_url: str | None = None, client: httpx.AsyncClient | None = None):
        self.api_key = api_key or os.getenv("AVALAI_API_KEY")
        self.model = model or os.getenv("AVALAI_MODEL", "gpt-4o-mini")
        self.base_url = (base_url or os.getenv("AVALAI_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        if not self.api_key or not self.model:
            raise AgentCallError("AVALAI_API_KEY or AVALAI_MODEL is missing.")
        if not self.base_url.startswith("https://") or not self.base_url.endswith("/v1"):
            raise AgentCallError("AVALAI_BASE_URL must be an HTTPS API v1 endpoint.")
        self.client = client

    async def complete(self, *, prompt_file: str, payload: dict[str, Any],
                       schema: type[BaseModel], retries: int = 1) -> BaseModel:
        if not 0 <= retries <= 2:
            raise ValueError("retries must be 0..2")
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
                        f"{self.base_url}/chat/completions",
                        headers={"Authorization": f"Bearer {self.api_key}",
                                 "Content-Type": "application/json"},
                        json={
                            "model": self.model,
                            "temperature": 0,
                            "max_tokens": 2400,
                            "response_format": {"type": "json_object"},
                            "messages": [
                                {"role": "system", "content": instructions},
                                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                            ],
                        },
                    )
                    response.raise_for_status()
                    data = response.json()
                    content = data["choices"][0]["message"]["content"]
                    return schema.model_validate(json.loads(content))
                except (httpx.HTTPError, ValueError, TypeError, KeyError,
                        IndexError, ValidationError):
                    if attempt == retries:
                        raise AgentCallError(
                            f"AvalAI structured response failed after {attempt + 1} attempts."
                        ) from None
            raise AgentCallError("No structured response returned.")
        finally:
            if own:
                await client.aclose()
