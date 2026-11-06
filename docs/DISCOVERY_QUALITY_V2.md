# Course Discovery Quality — source-first retrieval and evidence-backed explanations

The seventh live evaluation (10 extracted pages, 3 verified and scored courses) exposed three issues: a category/homepage was sometimes selected before a dedicated course detail, provider names in course pages were missed by the extraction Agent, and score rationales sometimes assumed a course language that the verified source did not establish.

## Adjustments
1. Search priority now scores dedicated `/course/...`, `/courses/...`, `/lesson/...` and `/product/...` URLs above bare homepages, catalog/browse pages, roadmap articles, PDFs and social videos. A match to the learner's actual topic also raises priority. Search result titles/snippets are only discovery hints, **never** accepted as course evidence.
2. Provider recovery is allowed only for an identifiable name suffix from the search result title that **also occurs in the retrieved course page text**. It will not overwrite a provider backed by evidence, or repair an existing forged evidence quote. Validation retains literal page matching for course name and provider, and requires at least one educational attribute.
3. The evaluation Agent is told not to infer language, price, modality, certificates or duration from the user preference. A deterministic display guard replaces explanations with a source-grounded fallback if they make unsupported claims about absent course fields. Unsupported limitations are discarded; confirmed user-preference gaps remain visible.
4. Existing adaptive page budget, six distinct providers for a complete report and scored **preliminary** report logic remain unchanged.

## Verification
Offline tests cover realistic result priority, corroborated provider recovery and a no-corroboration case, explicit forged-source rejection, and unsupported versus supported language/format explanation claims. These tests cannot prove a specific internet page is currently valid. Live acceptance still requires manually reviewing course URLs, providers, price, level and claims before presentation.

Do **not** increase the API page budget by default. The next authorized real smoke run can use the current 10-page cap, inspect `candidate_audit`, and compare verified courses, provider recovery and score explanation accuracy.
