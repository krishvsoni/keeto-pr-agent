import asyncio
from typing import Dict, Any, List, Callable, Optional
import time
from src.services.agent.agent import (
    LogicAgent,
    ReadabilityAgent,
    PerformanceAgent,
    SecurityAgent
)
from src.services.openrouter.api import OpenRouterService
from src.services.github.api import GitHubService
from src.models import ProgressType


class AgentOrchestrator:
    """Orchestrates multiple agents to review PR code with real-time progress tracking"""
    
    def __init__(self):
        self.llm_service = OpenRouterService()
        self.github_service = GitHubService()
        
        # Initialize all specialized agents
        self.agents = {
            "logic": LogicAgent(self.llm_service),
            "readability": ReadabilityAgent(self.llm_service),
            "performance": PerformanceAgent(self.llm_service),
            "security": SecurityAgent(self.llm_service)
        }
    
    async def review_pr(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        post_comments: bool = True,
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """
        Complete PR review workflow with optional progress tracking:
        1. Fetch PR details and diffs
        2. Run multi-agent analysis
        3. Aggregate findings
        4. Post comments back to PR (if enabled)
        
        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: PR number
            post_comments: Whether to post comments to GitHub
            progress_callback: Optional async callback for progress updates
        """
        try:
            await self._emit_progress(
                progress_callback, 
                ProgressType.STARTED,
                f"Starting review for PR #{pr_number} in {owner}/{repo}"
            )
            
            # Step 1: Fetch PR data
            await self._emit_progress(
                progress_callback,
                ProgressType.FETCHING_PR,
                "Fetching PR details and file changes from GitHub..."
            )
            
            pr_details = await self.github_service.get_pr_details(owner, repo, pr_number)
            pr_files = await self.github_service.get_pr_diff(owner, repo, pr_number)
            
            await self._emit_progress(
                progress_callback,
                ProgressType.PR_FETCHED,
                f"Retrieved PR details: {pr_details['changed_files']} files changed",
                {
                    "pr_title": pr_details['title'],
                    "files_count": pr_details['changed_files'],
                    "additions": pr_details['additions'],
                    "deletions": pr_details['deletions']
                }
            )
            
            # Step 2: Analyze each file with all agents
            all_findings = []
            files_to_review = [f for f in pr_files if not self._should_skip_file(f["filename"])]
            
            for idx, file_data in enumerate(files_to_review):
                await self._emit_progress(
                    progress_callback,
                    ProgressType.ANALYZING_FILE,
                    f"Analyzing file {idx + 1}/{len(files_to_review)}: {file_data['filename']}",
                    {"file": file_data['filename'], "progress": f"{idx + 1}/{len(files_to_review)}"}
                )
                
                # Run all agents in parallel for this file
                file_findings = await self._analyze_file_with_agents(
                    file_data,
                    pr_details,
                    progress_callback
                )
                all_findings.extend(file_findings)
                
                await self._emit_progress(
                    progress_callback,
                    ProgressType.FILE_ANALYZED,
                    f"Completed analysis of {file_data['filename']}: {len(file_findings)} findings",
                    {"file": file_data['filename'], "findings_count": len(file_findings)}
                )
            
            # Step 3: Generate summary
            await self._emit_progress(
                progress_callback,
                ProgressType.GENERATING_SUMMARY,
                "Generating comprehensive review summary..."
            )
            
            summary = self._generate_summary(all_findings, pr_details)
            
            # Step 4: Post comments if enabled
            if post_comments and all_findings:
                await self._emit_progress(
                    progress_callback,
                    ProgressType.POSTING_COMMENTS,
                    "Posting review comments to GitHub PR..."
                )
                
                await self._post_review_to_github(
                    owner, repo, pr_number, all_findings, summary
                )
            
            result = {
                "status": "success",
                "pr_number": pr_number,
                "files_reviewed": len(files_to_review),
                "total_findings": len(all_findings),
                "findings": all_findings,
                "summary": summary
            }
            
            await self._emit_progress(
                progress_callback,
                ProgressType.COMPLETED,
                f"Review complete! Analyzed {len(files_to_review)} files, found {len(all_findings)} issues",
                result
            )
            
            return result
        
        except Exception as e:
            error_msg = str(e)
            await self._emit_progress(
                progress_callback,
                ProgressType.ERROR,
                f"Error during review: {error_msg}",
                {"error": error_msg}
            )
            
            return {
                "status": "error",
                "error": error_msg,
                "pr_number": pr_number
            }
    
    async def _emit_progress(
        self,
        callback: Optional[Callable],
        progress_type: ProgressType,
        message: str,
        data: Optional[Dict[str, Any]] = None
    ):
        """Emit progress update if callback is provided"""
        if callback:
            await callback({
                "type": progress_type.value,
                "message": message,
                "data": data,
                "timestamp": time.time()
            })
    
    async def _analyze_file_with_agents(
        self,
        file_data: Dict[str, Any],
        pr_context: Dict[str, Any],
        progress_callback: Optional[Callable] = None
    ) -> List[Dict[str, Any]]:
        """Run all agents on a single file in parallel with progress tracking"""
        
        context = f"PR Title: {pr_context['title']}\nPR Description: {pr_context['description']}"
        
        # Track agent progress
        async def run_agent_with_tracking(agent_name: str, agent):
            await self._emit_progress(
                progress_callback,
                ProgressType.AGENT_ANALYZING,
                f"Running {agent_name} analysis on {file_data['filename']}...",
                {"agent": agent_name, "file": file_data['filename']}
            )
            
            result = await agent.analyze(file_data, context)
            
            await self._emit_progress(
                progress_callback,
                ProgressType.AGENT_COMPLETED,
                f"{agent_name.capitalize()} agent completed analysis",
                {
                    "agent": agent_name,
                    "file": file_data['filename'],
                    "has_issues": result.get("has_issues", False)
                }
            )
            
            return result
        
        # Run all agents concurrently
        tasks = [
            run_agent_with_tracking(name, agent)
            for name, agent in self.agents.items()
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out errors and files with no issues
        findings = []
        for result in results:
            if isinstance(result, dict) and result.get("has_issues"):
                findings.append(result)
        
        return findings
    
    def _should_skip_file(self, filename: str) -> bool:
        """Determine if file should be skipped from review"""
        skip_extensions = {
            '.json', '.lock', '.md', '.txt', '.yml', '.yaml',
            '.gitignore', '.env', '.png', '.jpg', '.gif', '.svg'
        }
        skip_patterns = [
            'package-lock.json',
            'yarn.lock',
            'poetry.lock',
            'requirements.txt'
        ]
        
        # Check extension
        for ext in skip_extensions:
            if filename.endswith(ext):
                return True
        
        # Check patterns
        for pattern in skip_patterns:
            if pattern in filename:
                return True
        
        return False
    
    def _generate_summary(
        self,
        findings: List[Dict[str, Any]],
        pr_details: Dict[str, Any]
    ) -> str:
        """Generate comprehensive human-readable summary of findings"""
        
        if not findings:
            return f"""## Code Review Complete - All Clear!

**PR #{pr_details['number']}: {pr_details['title']}**

All automated checks passed. No issues found by the AI review agents.

**Changes Summary:**
- Files changed: {pr_details['changed_files']}
- Lines added: +{pr_details['additions']}
- Lines removed: -{pr_details['deletions']}

The code changes look good from automated analysis perspectives:
- Logic & Correctness: No issues detected
- Code Readability: Meets standards
- Performance: No concerns identified
- Security: No vulnerabilities found
"""
        
        # Group by agent type and severity
        by_agent = {}
        severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
        
        for finding in findings:
            agent = finding.get("agent", "unknown")
            severity = finding.get("severity", "info")
            
            if agent not in by_agent:
                by_agent[agent] = []
            by_agent[agent].append(finding)
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
        
        summary_parts = [
            f"## AI Code Review Results",
            f"",
            f"**PR #{pr_details['number']}: {pr_details['title']}**",
            f"",
            f"**Changes:** {pr_details['changed_files']} files, +{pr_details['additions']}/-{pr_details['deletions']} lines",
            f"**Total Findings:** {len(findings)} issues detected",
            f"",
            f"**Severity Breakdown:**"
        ]
        
        # Add severity summary
        if severity_counts["critical"] > 0:
            summary_parts.append(f"- 🔴 Critical: {severity_counts['critical']}")
        if severity_counts["high"] > 0:
            summary_parts.append(f"- 🟠 High: {severity_counts['high']}")
        if severity_counts["medium"] > 0:
            summary_parts.append(f"- 🟡 Medium: {severity_counts['medium']}")
        if severity_counts["low"] > 0:
            summary_parts.append(f"- 🔵 Low: {severity_counts['low']}")
        
        summary_parts.append("")
        summary_parts.append("---")
        summary_parts.append("")
        
        # Add findings by category
        agent_names = {
            "security": "Security Analysis",
            "logic": "Logic & Correctness",
            "performance": "Performance Review",
            "readability": "Code Readability"
        }
        
        agent_emojis = {
            "security": "🔒",
            "logic": "🧠",
            "performance": "⚡",
            "readability": "📖"
        }
        
        for agent_type, agent_findings in by_agent.items():
            emoji = agent_emojis.get(agent_type, "•")
            name = agent_names.get(agent_type, agent_type.title())
            summary_parts.append(f"### {emoji} {name} ({len(agent_findings)} findings)")
            summary_parts.append("")
            
            for idx, finding in enumerate(agent_findings, 1):
                file_name = finding.get("file", "unknown")
                severity = finding.get("severity", "info")
                severity_label = severity.upper()
                
                summary_parts.append(f"#### {idx}. `{file_name}` - [{severity_label}]")
                summary_parts.append("")
                
                findings_text = finding.get("findings", "No details available")
                # Clean up findings text
                findings_text = findings_text.strip()
                if len(findings_text) > 800:
                    findings_text = findings_text[:800] + "...\n\n*[Findings truncated for summary]*"
                
                summary_parts.append(findings_text)
                summary_parts.append("")
                summary_parts.append("---")
                summary_parts.append("")
        
        summary_parts.append("")
        summary_parts.append("*Generated by AI PR Review Agent*")
        
        return "\n".join(summary_parts)
    
    async def _post_review_to_github(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        findings: List[Dict[str, Any]],
        summary: str
    ):
        """Post review comments to GitHub PR"""
        try:
            # Post summary as general comment
            await self.github_service.post_general_comment(
                owner, repo, pr_number, summary
            )
        except Exception as e:
            print(f"Failed to post review to GitHub: {str(e)}")
