# Course-source discovery diagnostic contract

## What prompted this change
A real Tavily/AvalAI smoke run returned six extracted pages but all six were classified by the Agent as non-course pages. The artifact lacked page URLs and rejection reasons, so discovery quality and classifier mistakes could not be distinguished.

## Changes
- Search results are ordered by a transparent course-detail-page heuristic with provider-domain diversification under a tight page budget. This ranking is **not verification**.
- Pages describing one real course can return a partial draft if audience/syllabus data is missing; the evidence validator still rejects incomplete records for final ranking.
- The extraction Agent uses a constrained rejection category rather than unstructured explanations.
- Per-candidate audit includes public URL without query parameters, truncated search title, selection flag, heuristic priority, extraction/verification status and a short categorical rejection reason.
- No source body, user description, API credential, provider response, or full LLM prompt appears in the diagnostic artifact.
- Hard budget constraints and six distinct providers remain mandatory.

## How to verify
Run `python -m pytest -q` with no external API calls. Then (only when authorized to spend credits) run the single-topic manual smoke workflow and inspect `candidate_audit` in `summary.json`.

A passing GitHub job by itself does not mean a complete report with six verified courses has been produced. The next real run is a diagnostic of retrieval versus classification; if most pages remain lists, search needs more targeted sources. If course pages are being rejected as lists, inspect prompt and extracted page text privately.

Note: GitHub Actions artifacts are accessible to repository collaborators; even with query parameters removed, their page titles and paths are public-source metadata and should be reviewed before external sharing.
