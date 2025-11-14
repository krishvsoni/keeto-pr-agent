"""PR Review Service - Fetches PR data and coordinates review."""
from typing import Dict, Any, List, Optional
from src.services.github.api import GitHubAPI
from src.services.github.url_parser import parse_github_pr_url
from src.services.agent.orchestrator import OrchestratorAgent


class PRReviewService:
    """Service to fetch PR data and orchestrate code review."""
    
    def __init__(self):
        """Initialize the review service."""
        self.github_api = GitHubAPI()
        self.orchestrator = OrchestratorAgent()
    
    def review_pr_from_url(
        self, 
        pr_url: str,
        selected_agents: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Review a PR given its GitHub URL.
        
        Args:
            pr_url: Full GitHub PR URL (e.g., https://github.com/owner/repo/pull/123)
            selected_agents: Optional list of specific agents to run
            
        Returns:
            Complete review report with all agent findings
        """
        try:
            # Parse PR URL
            url_info = parse_github_pr_url(pr_url)
            if not url_info:
                return {
                    "error": "Invalid GitHub PR URL",
                    "message": "URL must be in format: https://github.com/owner/repo/pull/number"
                }
            
            owner = url_info["owner"]
            repo = url_info["repo"]
            pr_number = url_info["pr_number"]
            
            # Fetch PR data from GitHub
            pr_data = self.github_api.get_pull_request(owner, repo, pr_number)
            if not pr_data:
                return {
                    "error": "Failed to fetch PR data",
                    "message": "Could not retrieve PR information from GitHub. Check the URL and your access token."
                }
            
            # Get PR diff
            diff = self.github_api.get_pull_request_diff(owner, repo, pr_number)
            if not diff:
                return {
                    "error": "Failed to fetch PR diff",
                    "message": "Could not retrieve PR changes from GitHub."
                }
            
            # Get the head SHA for fetching file contents
            head_sha = pr_data.get("head_sha", pr_data.get("head", {}).get("sha", ""))
            
            # Prepare PR info for agents
            pr_info = {
                "url": pr_url,
                "title": pr_data.get("title", ""),
                "description": pr_data.get("body", ""),
                "author": pr_data.get("user", {}).get("login", "unknown"),
                "state": pr_data.get("state", ""),
                "created_at": pr_data.get("created_at", ""),
                "updated_at": pr_data.get("updated_at", ""),
                "additions": pr_data.get("additions", 0),
                "deletions": pr_data.get("deletions", 0),
                "changed_files": pr_data.get("changed_files", 0),
                "owner": owner,
                "repo": repo,
                "pr_number": pr_number,
                "head_sha": head_sha
            }
            
            # Run orchestrator to review the PR
            review_result = self.orchestrator.review_pr(diff, pr_info, selected_agents)
            
            # Enrich issues with actual code context
            if review_result.get("issues"):
                self._enrich_issues_with_code_context(
                    review_result["issues"], 
                    owner, 
                    repo, 
                    head_sha
                )
            
            return review_result
            
        except Exception as e:
            return {
                "error": "Review failed",
                "message": str(e),
                "details": "An unexpected error occurred during PR review"
            }
    
    def review_pr_from_diff(
        self,
        diff: str,
        pr_info: Optional[Dict[str, Any]] = None,
        selected_agents: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Review a PR given a manual diff input.
        
        Args:
            diff: Git diff text
            pr_info: Optional PR metadata
            selected_agents: Optional list of specific agents to run
            
        Returns:
            Complete review report with all agent findings
        """
        try:
            # Use provided PR info or create minimal default
            if pr_info is None:
                pr_info = {
                    "title": "Manual Review",
                    "description": "Review from manually provided diff",
                    "author": "unknown",
                    "url": "manual"
                }
            
            # Run orchestrator
            review_result = self.orchestrator.review_pr(diff, pr_info, selected_agents)
            
            return review_result
            
        except Exception as e:
            return {
                "error": "Review failed",
                "message": str(e),
                "details": "An unexpected error occurred during diff review"
            }
    
    def get_available_agents(self) -> List[str]:
        """Get list of available review agents."""
        return self.orchestrator.get_available_agents()
    
    def _enrich_issues_with_code_context(
        self, 
        issues: List[Dict[str, Any]], 
        owner: str, 
        repo: str, 
        ref: str
    ) -> None:
        """
        Enrich issues with actual code context from the files.
        
        Args:
            issues: List of issues to enrich
            owner: Repository owner
            repo: Repository name
            ref: Git reference (commit SHA)
        """
        for issue in issues:
            file_path = issue.get("file")
            line_number = issue.get("line")
            
            if not file_path or not line_number:
                continue
            
            try:
                # Fetch the code context from GitHub
                context = self.github_api.get_file_lines_with_context(
                    owner=owner,
                    repo=repo,
                    file_path=file_path,
                    ref=ref,
                    line_number=line_number,
                    context_lines=3
                )
                
                if context:
                    # Add the original code at that line
                    issue["original_code"] = context["target_line"]
                    
                    # Add the full context for display
                    issue["code_context"] = {
                        "full_context": context["full_context"],
                        "start_line": context["context_start_line"],
                        "end_line": context["context_end_line"],
                        "target_line_number": line_number
                    }
                    
            except Exception as e:
                print(f"Failed to enrich issue with code context: {e}")
                # Continue without code context if fetching fails
                continue
