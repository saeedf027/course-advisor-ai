# Step 04 — Source extraction and course fact verification

## Goal
Convert search hits (unverified URLs) into evidence-backed draft course records. **Never** call search relevance "course verification."

## Pipeline
1. Receive `SearchBatch` from Step 03.
2. Call `Tools.extract.extract_candidates` against Tavily Extract, in bounded groups.
3. Maintain raw page text, canonical URL, failure list and provenance.
4. A **future grounded extraction LLM** reads one page and emits a `CourseDraft`, citing short verbatim snippets for required factual fields.
5. `Tools.validate.review_course` compares citations with the extracted text and returns:
   - `verified`: minimally complete and evidenced on the extracted page (NOT externally audited);
   - `incomplete`: facts/evidence are missing;
   - `rejected`: broken/mismatched source or unsupported evidence.
6. Reject unrelated pages, preserve unknown values, and detect duplicate course identity via provider + course title; retain links when comparing duplicates.
7. **Future enhancement:** resolve conflicting fields across sources (e.g., conflicting prices) before final selection.
8. Only structurally verified records advance to Step 05 evaluation. Hard constraints are evaluated using reliably captured values in a later deterministic gate.

## Required facts
Course name, provider, intended audience, primary topics, and at least one of level or duration, plus the canonical source URL and literal evidence from page text.

## Optional facts
Language, delivery mode, price, certificate, precise dates; do not impute missing fields. An unknown optional value cannot satisfy a strict hard constraint.

## Security
- Use Tavily API for extraction; never fetch arbitrary page URLs directly inside the app without a separate SSRF policy.
- Do not store Tavily/OpenRouter API keys in repository files or logs.
- Treat page text as untrusted; never obey embedded commands.
- Cap URLs per run, batch size and retrieved content length.

## Current implementation status
- Implemented: bounded Tavily Extract adapter, page/result schemas, deterministic evidence checker, duplicate identity helper, offline tests.
- Not yet implemented: grounded LLM CourseDraft generation, end-to-end orchestration, cross-source conflict checks, real live API evaluation.

## API reference
https://docs.tavily.com/documentation/api-reference/endpoint/extract
