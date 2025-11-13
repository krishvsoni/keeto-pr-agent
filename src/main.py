from fastapi import FastAPI, HTTPException, Request, BackgroundTasks, Header
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from typing import Optional
import uvicorn
import asyncio
import json
from pathlib import Path

from src.config import settings
from src.models import (
    PRReviewRequest,
    PRReviewResponse,
    HealthResponse,
    WebhookPayload,
    ChatReviewRequest,
    StreamReviewRequest,
    ProgressUpdate
)
from src.services.agent.enhanced_orchestrator import EnhancedAgentOrchestrator
from src.services.github.api import GitHubService
from src.services.github.url_parser import GitHubUrlParser


# Initialize FastAPI app
app = FastAPI(
    title="GitHub PR Review Agent with LangChain",
    description="Advanced code review system using LangChain-powered multi-agent analysis with critical thinking",
    version="2.0.0"
)

# Mount static files
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Initialize services
orchestrator = EnhancedAgentOrchestrator()
github_service = GitHubService()


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve chat interface"""
    html_file = Path(__file__).parent / "static" / "index.html"
    if html_file.exists():
        return FileResponse(html_file)
    return HTMLResponse(content="<h1>PR Review Agent</h1><p>Chat interface not found. Use /docs for API.</p>")


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Detailed health check with agent status"""
    return HealthResponse(
        status="healthy",
        service="PR Review Agent",
        version="1.0.0",
        agents=list(orchestrator.agents.keys())
    )


@app.post("/api/chat-review")
async def chat_review_pr(request: ChatReviewRequest):
    """
    Enhanced chat interface PR review endpoint with LangChain agents
    
    Supports:
    - Full PR URL: https://github.com/owner/repo/pull/123
    - Short format: owner/repo/123
    - Individual parameters: owner, repo, pr_number
    - Custom instructions for deep analysis
    
    Returns complete formatted analysis with agent thinking processes.
    """
    try:
        # Parse PR URL if provided, otherwise use individual fields
        if request.pr_url:
            try:
                parsed = GitHubUrlParser.parse(request.pr_url)
                owner = parsed.owner
                repo = parsed.repo
                pr_number = parsed.pr_number
            except ValueError as e:
                return {
                    "status": "error",
                    "error": str(e),
                    "pr_number": None
                }
        else:
            # Validate individual fields
            if not all([request.owner, request.repo, request.pr_number]):
                return {
                    "status": "error",
                    "error": "Please provide either pr_url or all of (owner, repo, pr_number)",
                    "pr_number": None
                }
            owner = request.owner
            repo = request.repo
            pr_number = request.pr_number
        
        # Run enhanced review with custom instructions
        result = await orchestrator.review_pr(
            owner=owner,
            repo=repo,
            pr_number=pr_number,
            custom_instructions=request.custom_instructions or "",
            post_comments=request.post_comments
        )
        
        return {
            "status": result["status"],
            "pr_number": result["pr_number"],
            "pr_url": result.get("pr_url"),
            "files_reviewed": result.get("files_reviewed"),
            "total_findings": result.get("total_findings"),
            "summary": result.get("summary"),
            "findings": result.get("findings", []),
            "custom_instructions_used": result.get("custom_instructions_used"),
            "error": result.get("error")
        }
    
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "pr_number": pr_number if 'pr_number' in locals() else None
        }


@app.post("/api/stream-review")
async def stream_review_pr(request: StreamReviewRequest):
    """
    Streaming PR review with real-time progress and LangChain agents
    
    Supports:
    - Full PR URL or individual parameters
    - Custom instructions for analysis
    - Real-time progress updates via SSE
    
    Returns Server-Sent Events (SSE) stream with detailed progress.
    """
    async def event_generator():
        try:
            # Parse PR URL if provided
            if request.pr_url:
                try:
                    parsed = GitHubUrlParser.parse(request.pr_url)
                    owner = parsed.owner
                    repo = parsed.repo
                    pr_number = parsed.pr_number
                except ValueError as e:
                    yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
                    return
            else:
                if not all([request.owner, request.repo, request.pr_number]):
                    yield f"data: {json.dumps({'type': 'error', 'message': 'Missing required parameters'})}\n\n"
                    return
                owner = request.owner
                repo = request.repo
                pr_number = request.pr_number
            
            # Queue to hold progress updates
            progress_queue = asyncio.Queue()
            
            async def progress_callback(update: dict):
                """Callback to receive progress updates"""
                await progress_queue.put(update)
            
            # Start review in background
            review_task = asyncio.create_task(
                orchestrator.review_pr(
                    owner=owner,
                    repo=repo,
                    pr_number=pr_number,
                    custom_instructions=request.custom_instructions or "",
                    post_comments=request.post_comments,
                    progress_callback=progress_callback
                )
            )
            
            # Stream progress updates as they come
            while not review_task.done():
                try:
                    # Wait for update with timeout
                    update = await asyncio.wait_for(progress_queue.get(), timeout=0.1)
                    
                    # Format as SSE
                    yield f"data: {json.dumps(update)}\n\n"
                    
                except asyncio.TimeoutError:
                    # No update yet, continue waiting
                    continue
            
            # Get any remaining updates
            while not progress_queue.empty():
                update = await progress_queue.get()
                yield f"data: {json.dumps(update)}\n\n"
            
            # Get final result
            result = await review_task
            
            # Send final result if not already sent via progress
            if result.get("status") == "error":
                yield f"data: {json.dumps({'type': 'error', 'message': result.get('error'), 'data': result})}\n\n"
            
        except Exception as e:
            error_data = {
                "type": "error",
                "message": f"Streaming error: {str(e)}",
                "data": {"error": str(e)}
            }
            yield f"data: {json.dumps(error_data)}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.post("/review", response_model=PRReviewResponse)
async def review_pr(request: PRReviewRequest):
    """
    Manually trigger PR review (API endpoint)
    
    Works with any GitHub repository - provide owner, repo, and PR number.
    The system will:
    1. Fetch PR details and code diffs from any public GitHub repository
    2. Run multi-agent analysis (logic, readability, performance, security)
    3. Generate structured review comments
    4. Optionally post comments back to GitHub (requires proper permissions)
    """
    try:
        result = await orchestrator.review_pr(
            owner=request.owner,
            repo=request.repo,
            pr_number=request.pr_number,
            post_comments=request.post_comments
        )
        
        return PRReviewResponse(
            status=result["status"],
            pr_number=result["pr_number"],
            files_reviewed=result.get("files_reviewed"),
            total_findings=result.get("total_findings"),
            summary=result.get("summary"),
            findings=result.get("findings"),
            error=result.get("error")
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/webhook")
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_github_event: Optional[str] = Header(None),
    x_hub_signature_256: Optional[str] = Header(None)
):
    """
    GitHub webhook endpoint for automated PR reviews
    
    Automatically triggers reviews when PRs are opened, updated, or reopened.
    Works with any GitHub repository that configures this webhook.
    
    Configure this endpoint in your GitHub repository settings:
    - Webhook URL: http://your-server:8000/webhook
    - Content type: application/json
    - Events: Pull requests
    - Secret: Configure in your environment as GITHUB_WEBHOOK_SECRET
    """
    
    # Get raw body for signature verification
    body = await request.body()
    
    # Verify webhook signature if secret is configured
    if x_hub_signature_256:
        if not github_service.verify_webhook_signature(body, x_hub_signature_256):
            raise HTTPException(status_code=401, detail="Invalid webhook signature")
    
    # Parse payload
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    
    # Handle pull request events
    if x_github_event == "pull_request":
        action = payload.get("action")
        
        # Trigger review for opened or synchronized PRs
        if action in ["opened", "synchronize", "reopened"]:
            pr_number = payload["pull_request"]["number"]
            repo_full_name = payload["repository"]["full_name"]
            owner, repo = repo_full_name.split("/")
            
            # Run review in background
            background_tasks.add_task(
                orchestrator.review_pr,
                owner=owner,
                repo=repo,
                pr_number=pr_number,
                post_comments=True
            )
            
            return JSONResponse(
                content={
                    "status": "accepted",
                    "message": f"Review queued for PR #{pr_number} in {owner}/{repo}"
                }
            )
    
    return JSONResponse(content={"status": "ignored", "event": x_github_event})


@app.post("/review-diff")
async def review_diff(
    file_path: str,
    code_diff: str,
    analysis_types: Optional[list[str]] = None
):
    """
    Review a code diff directly without GitHub integration
    
    Useful for:
    - Testing the review agents
    - Reviewing local changes before pushing
    - Integrating with other version control systems
    
    Supports all analysis types: logic, readability, performance, security
    """
    if not analysis_types:
        analysis_types = ["logic", "readability", "performance", "security"]
    
    try:
        results = []
        for analysis_type in analysis_types:
            if analysis_type in orchestrator.agents:
                agent = orchestrator.agents[analysis_type]
                file_data = {
                    "filename": file_path,
                    "patch": code_diff
                }
                result = await agent.analyze(file_data, "")
                if result.get("has_issues"):
                    results.append(result)
        
        return {
            "status": "success",
            "file": file_path,
            "total_findings": len(results),
            "analyses": results
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "message": str(exc),
            "path": str(request.url)
        }
    )


if __name__ == "__main__":
    uvicorn.run(
        "src.main:app",
        host=settings.host,
        port=settings.port,
        reload=True
    )
