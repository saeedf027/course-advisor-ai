# Course Advisor AI — PRD & Tech Stack summary (v1.1)

> Approved project decisions. This Markdown summary is not a replacement for the signed-off Word PRD.

## Product
Persian RTL AI course advisor using Workflow–Agent–Tools (WAT). The user can start with only a learning topic; progressively adding description, level, language, delivery mode, learning style, certificate preferences, budget, location, time available and course duration improves targeting. Optional preferences must be distinguished from hard constraints.

## Core output
- Six real online or in-person courses from different providers when sufficiently verified.
- One Persian paragraph per course with course name, provider, level or duration, target audience, key topics, relevance explanation and source link.
- User inputs used to generate the suggestions must appear in the report.
- **Beginners receive an additional step-by-step learning path**: prerequisites, ordered stages, goals, skills and references to suggested courses.
- Never fabricate missing courses, details or links; report insufficient verified results and offer to revise constraints.

## MVP boundaries
**In scope:** form, live course search, source checking, filtering, relevance assessment, RTL HTML report, conditional beginner path.
**Out of scope:** accounts, purchase/registration, full LMS integration, persistent user profile, comprehensive course database.
PDF can be produced as an optional follow-up via printing or HTML conversion.

## Confirmed tech
- Python 3.12+, FastAPI, Pydantic, HTML/CSS/JavaScript, Jinja2
- OpenRouter for LLM (model TBD)
- Tavily for search and extraction
- HTTPX, python-dotenv, pytest
- GitHub for version control
- No database, n8n, LangChain, or React required for MVP.

## WAT separation
- **Workflow:** deterministic Python orchestration, retries, errors and stage contracts.
- **Agent:** LLM decisions and relevance explanations.
- **Tools:** search, extract, validate and render operations.

## Current maturity
Input contract and example tests committed. No live end-to-end system or API connections yet. The previously approved Word PRD and standalone HTML UI prototype are separate design artifacts, pending binary transfer into this repository.
