from typing import Dict, Any, List, Optional
from src.services.openrouter.api import OpenRouterService
import re


class BaseReviewAgent:
    """Base class for all review agents with enhanced analysis capabilities"""
    
    def __init__(self, llm_service: OpenRouterService):
        self.llm_service = llm_service
        self.agent_type = "base"
        self.focus_areas = []
        self.severity_keywords = {
            "critical": ["crash", "exploit", "vulnerability", "sql injection", "xss", "authentication bypass"],
            "high": ["bug", "error", "incorrect", "security risk", "memory leak"],
            "medium": ["inefficient", "suboptimal", "should", "consider"],
            "low": ["style", "naming", "comment", "documentation"]
        }
    
    async def analyze(self, file_data: Dict[str, Any], context: str = "") -> Dict[str, Any]:
        """
        Analyze code and return structured findings
        
        Returns:
            Dict with structure:
            - agent: str - Agent type
            - file: str - Filename
            - findings: str - Detailed analysis
            - has_issues: bool - Whether issues were found
            - severity: str - Highest severity found
            - line_comments: List[Dict] - Line-specific comments
        """
        if not file_data.get("patch"):
            return {
                "agent": self.agent_type,
                "file": file_data["filename"],
                "findings": "No code changes to review",
                "has_issues": False,
                "severity": "none"
            }
        
        # Run LLM analysis
        result = await self.llm_service.analyze_code(
            code_diff=file_data["patch"],
            file_path=file_data["filename"],
            analysis_type=self.agent_type,
            context=context
        )
        
        # Enrich result with metadata
        result["agent"] = self.agent_type
        result["file"] = file_data["filename"]
        result["severity"] = self._determine_severity(result.get("findings", ""))
        result["line_comments"] = self._extract_line_comments(result.get("findings", ""), file_data.get("patch", ""))
        
        return result
    
    def _determine_severity(self, findings: str) -> str:
        """Determine highest severity level in findings"""
        findings_lower = findings.lower()
        
        for severity in ["critical", "high", "medium", "low"]:
            for keyword in self.severity_keywords[severity]:
                if keyword in findings_lower:
                    return severity
        
        return "info"
    
    def _extract_line_comments(self, findings: str, patch: str) -> List[Dict[str, Any]]:
        """Extract line-specific comments from findings"""
        comments = []
        
        # Look for line number references in findings
        line_pattern = r'line[s]?\s*(\d+)'
        matches = re.finditer(line_pattern, findings, re.IGNORECASE)
        
        for match in matches:
            line_num = int(match.group(1))
            # Extract context around the line mention
            start = max(0, match.start() - 100)
            end = min(len(findings), match.end() + 200)
            comment_text = findings[start:end].strip()
            
            comments.append({
                "line": line_num,
                "comment": comment_text,
                "severity": self._determine_severity(comment_text)
            })
        
        return comments


class LogicAgent(BaseReviewAgent):
    """Agent specialized in reviewing code logic and correctness"""
    
    def __init__(self, llm_service: OpenRouterService):
        super().__init__(llm_service)
        self.agent_type = "logic"
        self.focus_areas = [
            "Algorithmic correctness",
            "Edge case handling",
            "Null/undefined checks",
            "Loop invariants",
            "Conditional logic",
            "Error handling",
            "Type safety"
        ]


class ReadabilityAgent(BaseReviewAgent):
    """Agent specialized in reviewing code readability and maintainability"""
    
    def __init__(self, llm_service: OpenRouterService):
        super().__init__(llm_service)
        self.agent_type = "readability"
        self.focus_areas = [
            "Naming conventions",
            "Code structure",
            "Function complexity",
            "Documentation quality",
            "Code duplication",
            "Design patterns",
            "SOLID principles"
        ]


class PerformanceAgent(BaseReviewAgent):
    """Agent specialized in reviewing code performance"""
    
    def __init__(self, llm_service: OpenRouterService):
        super().__init__(llm_service)
        self.agent_type = "performance"
        self.focus_areas = [
            "Time complexity",
            "Space complexity",
            "Database query optimization",
            "Caching opportunities",
            "Unnecessary computations",
            "Memory management",
            "I/O operations"
        ]


class SecurityAgent(BaseReviewAgent):
    """Agent specialized in reviewing code security"""
    
    def __init__(self, llm_service: OpenRouterService):
        super().__init__(llm_service)
        self.agent_type = "security"
        self.focus_areas = [
            "Input validation",
            "SQL injection",
            "XSS vulnerabilities",
            "Authentication/Authorization",
            "Sensitive data exposure",
            "Cryptography",
            "Dependency vulnerabilities",
            "CSRF protection"
        ]
