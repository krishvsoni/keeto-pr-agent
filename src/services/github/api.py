import httpx
from github import Github
from typing import List, Dict, Any, Optional
from src.config import settings


class GitHubService:
    """Service for interacting with GitHub API"""
    
    def __init__(self):
        self.github = Github(settings.GITHUB_TOKEN)
        self.headers = {
            "Authorization": f"token {settings.GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }
    
    async def get_pr_details(self, owner: str, repo: str, pr_number: int) -> Dict[str, Any]:
        """Fetch PR details including metadata"""
        try:
            repo_obj = self.github.get_repo(f"{owner}/{repo}")
            pr = repo_obj.get_pull(pr_number)
            
            return {
                "number": pr.number,
                "title": pr.title,
                "description": pr.body or "",
                "author": pr.user.login,
                "state": pr.state,
                "created_at": pr.created_at.isoformat(),
                "updated_at": pr.updated_at.isoformat(),
                "head_sha": pr.head.sha,
                "base_branch": pr.base.ref,
                "head_branch": pr.head.ref,
                "commits": pr.commits,
                "additions": pr.additions,
                "deletions": pr.deletions,
                "changed_files": pr.changed_files
            }
        except Exception as e:
            raise Exception(f"Failed to fetch PR details: {str(e)}")
    
    async def get_pr_diff(self, owner: str, repo: str, pr_number: int) -> List[Dict[str, Any]]:
        """Fetch PR diff with file changes"""
        try:
            repo_obj = self.github.get_repo(f"{owner}/{repo}")
            pr = repo_obj.get_pull(pr_number)
            
            files_data = []
            for file in pr.get_files():
                files_data.append({
                    "filename": file.filename,
                    "status": file.status,
                    "additions": file.additions,
                    "deletions": file.deletions,
                    "changes": file.changes,
                    "patch": file.patch if hasattr(file, 'patch') else None,
                    "raw_url": file.raw_url,
                    "blob_url": file.blob_url
                })
            
            return files_data
        except Exception as e:
            raise Exception(f"Failed to fetch PR diff: {str(e)}")
    
    async def get_file_content(self, owner: str, repo: str, file_path: str, ref: str) -> str:
        """Get full file content at specific commit"""
        try:
            repo_obj = self.github.get_repo(f"{owner}/{repo}")
            content = repo_obj.get_contents(file_path, ref=ref)
            return content.decoded_content.decode('utf-8')
        except Exception as e:
            return f"Could not fetch file content: {str(e)}"
    
    async def post_review_comment(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        comments: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Post review comments to PR with improved error handling"""
        try:
            repo_obj = self.github.get_repo(f"{owner}/{repo}")
            pr = repo_obj.get_pull(pr_number)
            
            # Separate line-specific and general comments
            line_comments = []
            general_comments = []
            
            for comment in comments:
                if comment.get("line") and comment.get("path"):
                    line_comments.append(comment)
                else:
                    general_comments.append(comment)
            
            posted_count = 0
            failed_count = 0
            
            # Post line-specific comments
            if line_comments:
                commit = pr.get_commits()[pr.commits - 1]
                
                for lc in line_comments:
                    try:
                        pr.create_review_comment(
                            body=lc["body"],
                            commit=commit,
                            path=lc["path"],
                            line=lc["line"]
                        )
                        posted_count += 1
                    except Exception as e:
                        failed_count += 1
                        print(f"Failed to post comment on {lc['path']}:{lc['line']}: {str(e)}")
            
            # Post general review comment
            if general_comments:
                summary_parts = []
                for gc in general_comments:
                    summary_parts.append(gc.get("body", ""))
                
                summary = "\n\n".join(summary_parts)
                pr.create_issue_comment(f"## AI Code Review\n\n{summary}")
                posted_count += len(general_comments)
            
            return {
                "status": "success",
                "comments_posted": posted_count,
                "comments_failed": failed_count
            }
        
        except Exception as e:
            raise Exception(f"Failed to post review comments: {str(e)}")
    
    async def post_general_comment(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        body: str
    ) -> Dict[str, Any]:
        """Post a general comment to PR"""
        try:
            repo_obj = self.github.get_repo(f"{owner}/{repo}")
            pr = repo_obj.get_pull(pr_number)
            comment = pr.create_issue_comment(body)
            
            return {
                "status": "success",
                "comment_id": comment.id,
                "comment_url": comment.html_url
            }
        except Exception as e:
            raise Exception(f"Failed to post general comment: {str(e)}")
    
    def get_pull_request(self, owner: str, repo: str, pr_number: int) -> Optional[Dict[str, Any]]:
        """Get PR information synchronously."""
        try:
            repo_obj = self.github.get_repo(f"{owner}/{repo}")
            pr = repo_obj.get_pull(pr_number)
            
            return {
                "number": pr.number,
                "title": pr.title,
                "body": pr.body or "",
                "user": {"login": pr.user.login},
                "state": pr.state,
                "created_at": pr.created_at.isoformat(),
                "updated_at": pr.updated_at.isoformat(),
                "additions": pr.additions,
                "deletions": pr.deletions,
                "changed_files": pr.changed_files,
                "head_sha": pr.head.sha
            }
        except Exception as e:
            print(f"Error fetching PR: {e}")
            return None
    
    def get_pull_request_diff(self, owner: str, repo: str, pr_number: int) -> Optional[str]:
        """Get PR diff as a single string."""
        try:
            repo_obj = self.github.get_repo(f"{owner}/{repo}")
            pr = repo_obj.get_pull(pr_number)
            
            diff_parts = []
            for file in pr.get_files():
                if file.patch:
                    diff_parts.append(f"--- a/{file.filename}")
                    diff_parts.append(f"+++ b/{file.filename}")
                    diff_parts.append(file.patch)
                    diff_parts.append("")
            
            return "\n".join(diff_parts)
        except Exception as e:
            print(f"Error fetching PR diff: {e}")
            return None
    
    def get_file_lines_with_context(
        self, 
        owner: str, 
        repo: str, 
        file_path: str, 
        ref: str,
        line_number: int,
        context_lines: int = 3
    ) -> Optional[Dict[str, Any]]:
        """
        Get specific lines from a file with surrounding context.
        
        Args:
            owner: Repository owner
            repo: Repository name
            file_path: Path to the file
            ref: Git reference (commit SHA, branch name)
            line_number: Target line number (1-indexed)
            context_lines: Number of lines before and after to include
            
        Returns:
            Dict with line content, start/end line numbers, and full context
        """
        try:
            repo_obj = self.github.get_repo(f"{owner}/{repo}")
            content = repo_obj.get_contents(file_path, ref=ref)
            file_content = content.decoded_content.decode('utf-8')
            
            lines = file_content.split('\n')
            total_lines = len(lines)
            
            # Calculate range (0-indexed internally)
            start_idx = max(0, line_number - 1 - context_lines)
            end_idx = min(total_lines, line_number + context_lines)
            
            # Get the specific line and context
            target_line = lines[line_number - 1] if 0 <= line_number - 1 < total_lines else ""
            context_lines_list = lines[start_idx:end_idx]
            
            return {
                "file_path": file_path,
                "target_line": target_line,
                "target_line_number": line_number,
                "context_start_line": start_idx + 1,
                "context_end_line": end_idx,
                "context_lines": context_lines_list,
                "full_context": '\n'.join(context_lines_list)
            }
        except Exception as e:
            print(f"Error fetching file content: {e}")
            return None
    
    def get_pr_file_patches(self, owner: str, repo: str, pr_number: int) -> Dict[str, str]:
        """
        Get patches (diffs) for all files in a PR.
        
        Returns:
            Dict mapping file paths to their patch content
        """
        try:
            repo_obj = self.github.get_repo(f"{owner}/{repo}")
            pr = repo_obj.get_pull(pr_number)
            
            patches = {}
            for file in pr.get_files():
                if file.patch:
                    patches[file.filename] = file.patch
            
            return patches
        except Exception as e:
            print(f"Error fetching file patches: {e}")
            return {}

    
    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """Verify GitHub webhook signature"""
        import hmac
        import hashlib
        
        if not settings.GITHUB_WEBHOOK_SECRET:
            return True  # Skip verification if no secret is set
        
        mac = hmac.new(
            settings.GITHUB_WEBHOOK_SECRET.encode(),
            msg=payload,
            digestmod=hashlib.sha256
        )
        expected_signature = f"sha256={mac.hexdigest()}"
        return hmac.compare_digest(expected_signature, signature)


# Alias for convenience
GitHubAPI = GitHubService
