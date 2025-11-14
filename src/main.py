from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from typing import List, Optional
import os

from src.services.pr_review_service import PRReviewService

app = FastAPI(
    title="PR Review AI",
    description="AI-powered Pull Request review system with specialized agents",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="src/static"), name="static")

pr_review_service = PRReviewService()

class ReviewRequest(BaseModel):
    pr_url: str = Field(..., description="GitHub Pull Request URL")
    agents: Optional[List[str]] = Field(
        None, 
        description="List of specific agents to run. If omitted, all agents will run."
    )

class DiffReviewRequest(BaseModel):
    diff: str = Field(..., description="Git diff content")
    pr_title: Optional[str] = Field(None, description="PR title")
    pr_description: Optional[str] = Field(None, description="PR description")
    agents: Optional[List[str]] = Field(
        None,
        description="List of specific agents to run. If omitted, all agents will run."
    )

@app.get("/", response_class=HTMLResponse)
async def root():
    html_path = os.path.join("src", "static", "index.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>PR Review AI</h1><p>Frontend not found. Please access /api/docs for API documentation.</p>")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "PR Review AI"}

@app.get("/api/agents")
async def get_available_agents():
    agents = pr_review_service.get_available_agents()
    return {
        "agents": agents,
        "descriptions": {
            "security": "Identifies security vulnerabilities and risks",
            "logic": "Detects logic errors and runtime bugs",
            "performance": "Finds performance issues and inefficiencies",
            "readability": "Reviews code quality and maintainability",
            "test_coverage": "Identifies missing tests and edge cases"
        }
    }

@app.post("/api/review")
async def review_pull_request(request: ReviewRequest):
    try:
        result = pr_review_service.review_pr_from_url(
            pr_url=request.pr_url,
            selected_agents=request.agents
        )
        if "error" in result:
            raise HTTPException(
                status_code=400,
                detail=result
            )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Internal server error",
                "message": str(e)
            }
        )

@app.post("/api/review/diff")
async def review_diff(request: DiffReviewRequest):
    try:
        pr_info = None
        if request.pr_title or request.pr_description:
            pr_info = {
                "title": request.pr_title or "Manual Review",
                "description": request.pr_description or "",
                "author": "manual",
                "url": "manual"
            }
        result = pr_review_service.review_pr_from_diff(
            diff=request.diff,
            pr_info=pr_info,
            selected_agents=request.agents
        )
        if "error" in result:
            raise HTTPException(
                status_code=400,
                detail=result
            )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Internal server error",
                "message": str(e)
            }
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
