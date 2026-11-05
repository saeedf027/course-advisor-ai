"""Step 04A — retrieve page text through Tavily Extract.

This tool retrieves source text, NOT verified course facts. It never fetches
untrusted URLs from the local machine: the URLs are sent to Tavily's API.
"""
from __future__ import annotations

import os
from typing import Literal

import httpx
from pydantic import Field
from app.schemas import StrictModel
from Tools.search import SearchBatch, canonical_url

EXTRACT_ENDPOINT = "https://api.tavily.com/extract"


class ExtractedPage(StrictModel):
    url: str
    raw_content: str = Field(min_length=1)
    extract_status: Literal["retrieved"] = "retrieved"


class ExtractionBatch(StrictModel):
    pages: list[ExtractedPage] = Field(default_factory=list)
    failed_urls: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


async def extract_candidates(
    candidates: SearchBatch,
    api_key: str | None = None,
    client: httpx.AsyncClient | None = None,
    batch_size: int = 5,
    max_urls: int = 30,
    max_chars_per_page: int = 30000,
) -> ExtractionBatch:
    """Use bounded batches to extract candidate content with Tavily.

    Successful extraction does not imply that any course claim is verified.
    """
    key = api_key or os.getenv("TAVILY_API_KEY")
    if not key:
        raise RuntimeError("TAVILY_API_KEY is not configured.")
    if not 1 <= batch_size <= 20 or not 1 <= max_urls <= 100:
        raise ValueError("Invalid extraction limits.")
    if max_chars_per_page < 500:
        raise ValueError("max_chars_per_page must be at least 500.")
    urls = list(dict.fromkeys(
        normalized for item in candidates.candidates
        if (normalized := canonical_url(item.url)) is not None
    ))[:max_urls]
    own_client = client is None
    if own_client:
        client = httpx.AsyncClient(timeout=40)
    pages: dict[str, ExtractedPage] = {}
    failed: list[str] = []
    errors: list[str] = []
    try:
        for offset in range(0, len(urls), batch_size):
            group = urls[offset:offset + batch_size]
            try:
                response = await client.post(
                    EXTRACT_ENDPOINT,
                    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                    json={"urls": group, "extract_depth": "basic",
                          "format": "markdown", "include_images": False},
                )
                response.raise_for_status()
                body = response.json()
                if not isinstance(body, dict) or not isinstance(body.get("results"), list):
                    raise ValueError("Unexpected Tavily Extract response.")
                for record in body["results"]:
                    if not isinstance(record, dict):
                        continue
                    url = canonical_url(record.get("url", ""))
                    content = record.get("raw_content")
                    if url in group and isinstance(content, str) and content.strip():
                        pages[url] = ExtractedPage(url=url, raw_content=content[:max_chars_per_page])
                for record in body.get("failed_results", []):
                    if isinstance(record, dict):
                        bad_url = canonical_url(record.get("url", ""))
                        if bad_url in group:
                            failed.append(bad_url)
                failed.extend(url for url in group if url not in pages and url not in failed)
            except (httpx.HTTPError, ValueError):
                errors.append(f"Extraction batch {offset // batch_size + 1} failed.")
                failed.extend(group)
        return ExtractionBatch(pages=list(pages.values()),
                               failed_urls=list(dict.fromkeys(failed)), errors=errors)
    finally:
        if own_client:
            await client.aclose()
