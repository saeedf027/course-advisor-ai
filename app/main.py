"""FastAPI wrapper for the orchestrated WAT report pipeline.

The public deployment needs authentication/rate limits before accepting
untrusted internet traffic because each request can consume API credits.
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from app.schemas import CourseAdvisorInput
from Workflow.runner import Pipeline, PipelineError
from Agent.client import AgentCallError

app = FastAPI(title="Course Advisor AI", version="0.1.0")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/report", response_class=HTMLResponse)
async def report(request: CourseAdvisorInput):
    try:
        result = await Pipeline().run(request)
    except (PipelineError, AgentCallError, ValueError) as exc:
        raise HTTPException(status_code=502,
                            detail=f"Report generation failed ({type(exc).__name__}).") from None
    return HTMLResponse(result.report_html, headers={"Cache-Control": "no-store"})
