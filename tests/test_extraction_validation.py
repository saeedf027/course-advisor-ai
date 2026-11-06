"""Offline tests — no API keys or paid Tavily calls."""
import asyncio
import httpx
from Tools.search import SearchBatch, CandidatePage
from Tools.extract import extract_candidates
from Tools.validate import CourseDraft, Evidence, review_course, course_identity

URL = "https://academy.example.org/courses/data-101"
CONTENT = "Course: Data 101\nProvider: Example Academy\nAudience: Beginners\nTopics: Spreadsheets, charts\nLevel: Beginner"


def sample_draft():
    return CourseDraft(
        name="Data 101", provider="Example Academy", audience="Beginners",
        topics=["Spreadsheets", "charts"], level="Beginner", source_url=URL,
        evidence=[
            Evidence(field="name", source_url=URL, quote="Data 101"),
            Evidence(field="provider", source_url=URL, quote="Example Academy"),
            Evidence(field="audience", source_url=URL, quote="Beginners"),
            Evidence(field="topics", source_url=URL, quote="Spreadsheets, charts"),
            Evidence(field="level", source_url=URL, quote="Level: Beginner"),
        ],
    )


def test_verified_only_with_literal_evidence():
    assert review_course(sample_draft(), CONTENT, URL).status == "verified"


def test_missing_evidence_is_incomplete():
    draft = sample_draft().model_copy(update={"evidence": []})
    assert review_course(draft, CONTENT, URL).status == "incomplete"


def test_fabricated_quote_is_rejected():
    draft = sample_draft()
    draft.evidence[0].quote = "This never appears on the page"
    assert review_course(draft, CONTENT, URL).status == "rejected"


def test_mismatched_url_is_rejected():
    assert review_course(sample_draft(), CONTENT, "https://other.example.org/x").status == "rejected"


def test_duplicate_course_identity():
    other = sample_draft().model_copy(update={"source_url": "https://example.net/another"})
    assert course_identity(sample_draft()) == course_identity(other)


def test_extract_with_mocked_tavily_response():
    batch = SearchBatch(candidates=[
        CandidatePage(url=URL, title="Course page", snippet="Course details")
    ], searched_queries=["data analysis course"], total_results_before_dedup=1)

    def handler(request):
        assert request.url == "https://api.tavily.com/extract"
        return httpx.Response(200, json={
            "results": [{"url": URL, "raw_content": CONTENT}],
            "failed_results": [],
        })

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await extract_candidates(batch, api_key="test-key", client=client)
    result = asyncio.run(run())
    assert len(result.pages) == 1
    assert result.pages[0].raw_content == CONTENT
    assert result.failed_urls == []

def test_provider_recovery_requires_literal_page_corroboration():
    from Tools.validate import recover_provider_from_page
    url = "https://academy.example.org/course/data"
    draft = CourseDraft(
        name="تحلیل داده", provider=None, level="مقدماتی",
        source_url=url,
        evidence=[
            Evidence(field="name", source_url=url, quote="تحلیل داده"),
            Evidence(field="level", source_url=url, quote="مقدماتی"),
        ],
    )
    title = "دوره تحلیل داده | سون‌لرن"
    raw = "تحلیل داده، سطح مقدماتی؛ برگزارکننده سون‌لرن"
    recovered = recover_provider_from_page(draft, raw, title)
    assert recovered.provider == "سون‌لرن"
    assert any(e.field == "provider" for e in recovered.evidence)
    assert review_course(recovered, raw, url).status == "verified"
    no_corroboration = recover_provider_from_page(
        draft, "تحلیل داده، مقدماتی", title
    )
    assert no_corroboration.provider is None


def test_provider_recovery_does_not_override_forged_identity_evidence():
    from Tools.validate import recover_provider_from_page
    url = "https://academy.example.org/course/data"
    draft = CourseDraft(
        name="Data Course", provider="Other Institute", level="Beginner",
        source_url=url,
        evidence=[
            Evidence(field="name", source_url=url, quote="Data Course"),
            Evidence(field="level", source_url=url, quote="Beginner"),
            Evidence(field="provider", source_url=url, quote="Imaginary Institute"),
        ],
    )
    raw = "Data Course Beginner, offered by Example Academy."
    result = recover_provider_from_page(draft, raw, "Data Course | Example Academy")
    assert result.provider == "Other Institute"
    assert review_course(result, raw, url).status == "rejected"
