import httpx
from github import Github
from typing import List, Dict, Any, Optional
from src.config import settings


class GitHubService:
    """Service for interacting with GitHub API"""
    
    def __init__(self):
        self.github = Github(settings.github_token)
        self.headers = {
            "Authorization": f"token {settings.github_token}",
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
    
    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """Verify GitHub webhook signature"""
        import hmac
        import hashlib
        
        if not settings.github_webhook_secret:
            return True  # Skip verification if no secret is set
        
        mac = hmac.new(
            settings.github_webhook_secret.encode(),
            msg=payload,
            digestmod=hashlib.sha256
        )
        expected_signature = f"sha256={mac.hexdigest()}"
        return hmac.compare_digest(expected_signature, signature)
