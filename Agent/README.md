# Agent — design stage

Planned LLM provider: OpenRouter; the exact model is not yet chosen.

Responsibilities:
- Interpret optional user context without assuming omitted facts.
- Infer beginner status only where supported by input.
- Suggest search queries and analyze educational fit.
- Write concise Persian explanations grounded in verified course records.
- Generate an ordered beginner learning path when needed.

The LLM cannot override hard constraints or invent course details. Prompts and schemas will be designed in the next stages. No working agent is implemented yet.
