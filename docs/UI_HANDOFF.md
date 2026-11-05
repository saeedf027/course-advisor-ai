# UI prototype handoff

The product UI design was approved as **Course Advisor UI v1.2** (standalone Persian RTL HTML with Vazir/Vazirmatn styling, embedded fantasy hero image, user preferences, mock six-course results and beginner roadmap).

**Current status:** the approved standalone HTML exists as a conversation artifact, but has not been committed here yet. It is approximately 2.7 MB because of the embedded image. No connection to live search/LLM has been built. Avoid describing it as production-ready.

Expected UI-to-API mapping: form fields → `CourseAdvisorInput` in `app/schemas.py`. The existing UI's string-based weekly time options need to be normalized to numeric `weekly_hours` (or the contract revised) during integration.
