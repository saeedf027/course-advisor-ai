# Workflow — design stage

The workflow engine is **Python**, not n8n. Its future implementation will live in this folder.

## Agreed processing stages (not yet implemented)
1. Receive and validate the UI form data with Pydantic.
2. Interpret the user's learning needs using an LLM agent.
3. Build search queries based on topic, preferences, and hard constraints.
4. Search live web sources (planned: Tavily).
5. Extract course facts and verify sources.
6. Deduplicate and filter invalid courses.
7. Evaluate fit and select **exactly six verified courses** when available.
8. For beginners, generate a stepwise learning path with prerequisites.
9. Render a Persian RTL HTML report including the original input.

**Safety/quality rule:** Never invent courses or citations to fill six slots. If fewer than six verifiable options exist, retry searching or return an explicit insufficiency status.

## Next step
Specify step-by-step data contracts, retries, timeouts, decision points, agent inputs/outputs and implementation in `runner.py`.
