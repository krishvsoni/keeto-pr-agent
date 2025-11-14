"""GitHub PR URL parser utility"""
import re
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class ParsedPRUrl(BaseModel):
    """Parsed GitHub PR URL information"""
    owner: str = Field(..., description="Repository owner")
    repo: str = Field(..., description="Repository name")
    pr_number: int = Field(..., description="Pull request number")
    url: str = Field(..., description="Original URL")


class GitHubUrlParser:
    """Parse GitHub PR URLs and extract repository information"""
    
    # Various GitHub PR URL patterns
    PATTERNS = [
        # Standard: https://github.com/owner/repo/pull/123
        r'https?://github\.com/([^/]+)/([^/]+)/pull/(\d+)',
        # With trailing slash: https://github.com/owner/repo/pull/123/
        r'https?://github\.com/([^/]+)/([^/]+)/pull/(\d+)/',
        # With fragments/queries: https://github.com/owner/repo/pull/123#issuecomment-123
        r'https?://github\.com/([^/]+)/([^/]+)/pull/(\d+)[#?]',
        # Short format (less common): github.com/owner/repo/pull/123
        r'github\.com/([^/]+)/([^/]+)/pull/(\d+)',
    ]
    
    @classmethod
    def parse(cls, pr_input: str) -> ParsedPRUrl:
        """
        Parse GitHub PR URL or direct input
        
        Args:
            pr_input: Can be:
                - Full URL: https://github.com/owner/repo/pull/123
                - Short format: owner/repo/123
                - Just PR number if owner/repo provided separately
        
        Returns:
            ParsedPRUrl object with extracted information
            
        Raises:
            ValueError: If URL cannot be parsed
        """
        pr_input = pr_input.strip()
        
        # Try URL patterns
        for pattern in cls.PATTERNS:
            match = re.search(pattern, pr_input)
            if match:
                owner, repo, pr_number = match.groups()
                return ParsedPRUrl(
                    owner=owner,
                    repo=repo,
                    pr_number=int(pr_number),
                    url=pr_input
                )
        
        # Try short format: owner/repo/123 or owner/repo#123
        short_match = re.match(r'^([^/\s]+)/([^/\s]+)[/#](\d+)$', pr_input)
        if short_match:
            owner, repo, pr_number = short_match.groups()
            return ParsedPRUrl(
                owner=owner,
                repo=repo,
                pr_number=int(pr_number),
                url=f"https://github.com/{owner}/{repo}/pull/{pr_number}"
            )
        
        # If just a number is provided, raise error asking for more info
        if pr_input.isdigit():
            raise ValueError(
                "Please provide the full GitHub PR URL (e.g., https://github.com/owner/repo/pull/123) "
                "or use format 'owner/repo/123'"
            )
        
        raise ValueError(
            f"Could not parse PR URL: '{pr_input}'. "
            "Expected format: https://github.com/owner/repo/pull/123 or owner/repo/123"
        )
    
    @classmethod
    def extract_from_text(cls, text: str) -> Optional[ParsedPRUrl]:
        """
        Extract PR URL from any text (e.g., chat message)
        
        Args:
            text: Text that may contain a GitHub PR URL
            
        Returns:
            ParsedPRUrl if found, None otherwise
        """
        for pattern in cls.PATTERNS:
            match = re.search(pattern, text)
            if match:
                owner, repo, pr_number = match.groups()
                url_start = match.start()
                url_end = match.end()
                
                # Try to get the full URL including any trailing parts
                full_url_match = re.search(
                    r'https?://github\.com/[^\s]+/pull/\d+[^\s]*',
                    text
                )
                url = full_url_match.group(0) if full_url_match else text[url_start:url_end]
                
                return ParsedPRUrl(
                    owner=owner,
                    repo=repo,
                    pr_number=int(pr_number),
                    url=url
                )
        
        return None
    
    @classmethod
    def validate_url(cls, pr_input: str) -> bool:
        """Check if input is a valid GitHub PR URL"""
        try:
            cls.parse(pr_input)
            return True
        except ValueError:
            return False


# Convenience functions for backward compatibility
def parse_pr_url(url: str) -> Dict[str, Any]:
    """Parse PR URL and return dict (legacy interface)"""
    parsed = GitHubUrlParser.parse(url)
    return {
        "owner": parsed.owner,
        "repo": parsed.repo,
        "pr_number": parsed.pr_number
    }


def parse_github_pr_url(url: str) -> Optional[Dict[str, Any]]:
    """Parse GitHub PR URL and return dict."""
    try:
        parsed = GitHubUrlParser.parse(url)
        return {
            "owner": parsed.owner,
            "repo": parsed.repo,
            "pr_number": parsed.pr_number,
            "url": parsed.url
        }
    except ValueError:
        return None


def extract_pr_from_text(text: str) -> Optional[Dict[str, Any]]:
    """Extract PR info from text (legacy interface)"""
    parsed = GitHubUrlParser.extract_from_text(text)
    if parsed:
        return {
            "owner": parsed.owner,
            "repo": parsed.repo,
            "pr_number": parsed.pr_number
        }
    return None
