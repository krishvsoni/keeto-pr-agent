from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum


class ProgressType(str, Enum):
    """Types of progress updates during PR review"""
    STARTED = "started"
    FETCHING_PR = "fetching_pr"
    PR_FETCHED = "pr_fetched"
    ANALYZING_FILE = "analyzing_file"
    FILE_ANALYZED = "file_analyzed"
    AGENT_ANALYZING = "agent_analyzing"
    AGENT_COMPLETED = "agent_completed"
    GENERATING_SUMMARY = "generating_summary"
    POSTING_COMMENTS = "posting_comments"
    COMPLETED = "completed"
    ERROR = "error"


class SeverityLevel(str, Enum):
    """Severity levels for findings"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class Finding(BaseModel):
    """Individual code review finding"""
    agent: str = Field(..., description="Agent that generated the finding")
    file: str = Field(..., description="File path")
    severity: SeverityLevel = Field(..., description="Severity level")
    findings: str = Field(..., description="Detailed finding description")
    has_issues: bool = Field(default=True, description="Whether issues were found")
    line_comments: Optional[List[Dict[str, Any]]] = Field(default=None, description="Line-specific comments")


class PRReviewRequest(BaseModel):
    """Request model for manual PR review"""
    owner: str = Field(..., description="Repository owner", example="facebook")
    repo: str = Field(..., description="Repository name", example="react")
    pr_number: int = Field(..., description="Pull request number", example=123)
    post_comments: bool = Field(default=True, description="Whether to post comments to GitHub")


class ChatReviewRequest(BaseModel):
    """Request model for chat interface PR review - supports full PR URL"""
    pr_url: Optional[str] = Field(default=None, description="Full GitHub PR URL (e.g., https://github.com/owner/repo/pull/123)")
    owner: Optional[str] = Field(default=None, description="Repository owner (if not using pr_url)", example="facebook")
    repo: Optional[str] = Field(default=None, description="Repository name (if not using pr_url)", example="react")
    pr_number: Optional[int] = Field(default=None, description="Pull request number (if not using pr_url)", example=123)
    custom_instructions: Optional[str] = Field(default=None, description="Custom instructions for deep analysis")
    post_comments: bool = Field(default=False, description="Whether to post comments to GitHub")


class StreamReviewRequest(BaseModel):
    """Request model for streaming PR review - supports full PR URL"""
    pr_url: Optional[str] = Field(default=None, description="Full GitHub PR URL")
    owner: Optional[str] = Field(default=None, description="Repository owner (if not using pr_url)", example="facebook")
    repo: Optional[str] = Field(default=None, description="Repository name (if not using pr_url)", example="react")
    pr_number: Optional[int] = Field(default=None, description="Pull request number (if not using pr_url)", example=123)
    custom_instructions: Optional[str] = Field(default=None, description="Custom instructions for deep analysis")
    post_comments: bool = Field(default=False, description="Whether to post comments to GitHub")


class ProgressUpdate(BaseModel):
    """Model for progress updates during streaming"""
    type: ProgressType = Field(..., description="Type of progress update")
    message: str = Field(..., description="Human-readable progress message")
    data: Optional[Dict[str, Any]] = Field(default=None, description="Additional data")
    timestamp: Optional[float] = Field(default=None, description="Unix timestamp")


class PRReviewResponse(BaseModel):
    """Response model for PR review"""
    status: str = Field(..., description="Review status")
    pr_number: int = Field(..., description="PR number")
    files_reviewed: Optional[int] = Field(default=None, description="Number of files reviewed")
    total_findings: Optional[int] = Field(default=None, description="Total findings count")
    summary: Optional[str] = Field(default=None, description="Review summary")
    findings: Optional[List[Dict[str, Any]]] = Field(default=None, description="Detailed findings")
    error: Optional[str] = Field(default=None, description="Error message if failed")


class WebhookPayload(BaseModel):
    """GitHub webhook payload"""
    action: str
    number: int
    pull_request: Dict[str, Any]
    repository: Dict[str, Any]


class HealthResponse(BaseModel):
    """Health check response"""
    status: str = Field(..., description="Service status")
    service: str = Field(..., description="Service name")
    version: str = Field(..., description="Service version")
    agents: Optional[List[str]] = Field(default=None, description="Available agents")
