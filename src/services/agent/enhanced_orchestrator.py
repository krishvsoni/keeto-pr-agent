"""Enhanced orchestrator with LangChain agents and custom instructions support"""
import asyncio
from typing import Dict, Any, List, Callable, Optional
import time
from src.services.agent.langchain_agents import (
    LogicReviewAgent,
    ReadabilityReviewAgent,
    PerformanceReviewAgent,
    SecurityReviewAgent
)
from src.services.github.api import GitHubService
from src.services.github.url_parser import GitHubUrlParser, ParsedPRUrl
from src.models import ProgressType


class EnhancedAgentOrchestrator:
    """
    Enhanced orchestrator using LangChain agents with critical thinking
    Supports custom instructions and detailed reasoning traces
    """
    
    def __init__(self):
        self.github_service = GitHubService()
        
        self.agents = {
            "logic": LogicReviewAgent(),
            "readability": ReadabilityReviewAgent(),
            "performance": PerformanceReviewAgent(),
            "security": SecurityReviewAgent()
        }
    
    async def review_pr_from_url(
        self,
        pr_url: str,
        custom_instructions: str = "",
        post_comments: bool = False,
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """
        Review PR from URL with custom instructions
        
        Args:
            pr_url: Full GitHub PR URL or short format (owner/repo/123)
            custom_instructions: User-provided instructions for deep analysis
            post_comments: Whether to post comments to GitHub
            progress_callback: Optional async callback for progress updates
        """
        try:
            parsed = GitHubUrlParser.parse(pr_url)
            
            return await self.review_pr(
                owner=parsed.owner,
                repo=parsed.repo,
                pr_number=parsed.pr_number,
                custom_instructions=custom_instructions,
                post_comments=post_comments,
                progress_callback=progress_callback
            )
        except ValueError as e:
            return {
                "status": "error",
                "error": f"Invalid PR URL: {str(e)}",
                "pr_number": None
            }
    
    async def review_pr(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        custom_instructions: str = "",
        post_comments: bool = False,
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """
        Complete PR review workflow with LangChain agents
        
        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: PR number
            custom_instructions: User-provided instructions for agents
            post_comments: Whether to post comments to GitHub
            progress_callback: Optional async callback for progress updates
        """
        try:
            await self._emit_progress(
                progress_callback, 
                ProgressType.STARTED,
                f"Starting deep review for PR #{pr_number} in {owner}/{repo}"
            )
            
            await self._emit_progress(
                progress_callback,
                ProgressType.FETCHING_PR,
                "Fetching PR details and file changes from GitHub..."
            )
            
            pr_details = await self.github_service.get_pr_details(owner, repo, pr_number)
            pr_files = await self.github_service.get_pr_diff(owner, repo, pr_number)
            
            pr_context = self._build_pr_context(pr_details, custom_instructions)
            
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
            
            all_findings = []
            files_to_review = [f for f in pr_files if not self._should_skip_file(f["filename"])]
            
            if not files_to_review:
                return {
                    "status": "success",
                    "pr_number": pr_number,
                    "files_reviewed": 0,
                    "total_findings": 0,
                    "findings": [],
                    "summary": "No code files to review in this PR."
                }
            
            for idx, file_data in enumerate(files_to_review):
                await self._emit_progress(
                    progress_callback,
                    ProgressType.ANALYZING_FILE,
                    f"Analyzing file {idx + 1}/{len(files_to_review)}: {file_data['filename']}",
                    {"file": file_data['filename'], "progress": f"{idx + 1}/{len(files_to_review)}"}
                )
                
                file_findings = await self._analyze_file_with_agents(
                    file_data,
                    pr_context,
                    custom_instructions,
                    progress_callback
                )
                all_findings.extend(file_findings)
                
                findings_count = len([f for f in file_findings if f.get("has_issues", False)])
                await self._emit_progress(
                    progress_callback,
                    ProgressType.FILE_ANALYZED,
                    f"Completed analysis of {file_data['filename']}: {findings_count} agents found issues",
                    {"file": file_data['filename'], "findings_count": findings_count}
                )
            
            await self._emit_progress(
                progress_callback,
                ProgressType.GENERATING_SUMMARY,
                "Generating comprehensive review summary with agent insights..."
            )
            
            summary = self._generate_detailed_summary(all_findings, pr_details, custom_instructions)
            
            if post_comments and all_findings:
                await self._emit_progress(
                    progress_callback,
                    ProgressType.POSTING_COMMENTS,
                    "Posting review comments to GitHub PR..."
                )
                
                try:
                    await self._post_review_to_github(
                        owner, repo, pr_number, all_findings, summary
                    )
                except Exception as e:
                    print(f"Warning: Failed to post to GitHub: {str(e)}")
            
            result = {
                "status": "success",
                "pr_number": pr_number,
                "pr_url": f"https://github.com/{owner}/{repo}/pull/{pr_number}",
                "files_reviewed": len(files_to_review),
                "total_findings": len([f for f in all_findings if f.get("has_issues", False)]),
                "findings": all_findings,
                "summary": summary,
                "custom_instructions_used": custom_instructions if custom_instructions else None
            }
            
            await self._emit_progress(
                progress_callback,
                ProgressType.COMPLETED,
                f"Review complete! Analyzed {len(files_to_review)} files"
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
    
    def _build_pr_context(self, pr_details: Dict[str, Any], custom_instructions: str) -> str:
        """Build comprehensive context for agents"""
        context_parts = [
            f"PR Title: {pr_details['title']}",
            f"Author: {pr_details['author']}",
            f"Description: {pr_details['description'] or 'No description provided'}",
            f"Changes: {pr_details['changed_files']} files, +{pr_details['additions']}/-{pr_details['deletions']} lines"
        ]
        
        if custom_instructions:
            context_parts.append(f"\nReviewer Instructions: {custom_instructions}")
        
        return "\n".join(context_parts)
    
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
        pr_context: str,
        custom_instructions: str,
        progress_callback: Optional[Callable] = None
    ) -> List[Dict[str, Any]]:
        """Run all LangChain agents on a single file in parallel"""
        
        async def run_agent_with_tracking(agent_name: str, agent):
            await self._emit_progress(
                progress_callback,
                ProgressType.AGENT_ANALYZING,
                f"{agent_name.capitalize()} agent analyzing {file_data['filename']}...",
                {"agent": agent_name, "file": file_data['filename']}
            )
            
            result = await agent.analyze(
                file_data=file_data,
                custom_instructions=custom_instructions,
                context=pr_context
            )
            
            await self._emit_progress(
                progress_callback,
                ProgressType.AGENT_COMPLETED,
                f"{agent_name.capitalize()} agent completed",
                {
                    "agent": agent_name,
                    "file": file_data['filename'],
                    "has_issues": result.get("has_issues", False),
                    "severity": result.get("severity", "none")
                }
            )
            
            return result
        
        tasks = [
            run_agent_with_tracking(name, agent)
            for name, agent in self.agents.items()
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        findings = []
        for result in results:
            if isinstance(result, dict):
                findings.append(result)
            elif isinstance(result, Exception):
                print(f"Agent error: {str(result)}")
        
        return findings
    
    def _should_skip_file(self, filename: str) -> bool:
        """Determine if file should be skipped from review"""
        skip_extensions = {
            '.json', '.lock', '.md', '.txt', '.yml', '.yaml',
            '.gitignore', '.env', '.png', '.jpg', '.gif', '.svg',
            '.ico', '.pdf', '.woff', '.woff2', '.ttf', '.eot'
        }
        skip_patterns = [
            'package-lock.json',
            'yarn.lock',
            'poetry.lock',
            'Pipfile.lock',
            'requirements.txt',
            'node_modules/',
            '.min.js',
            '.min.css'
        ]
        
        filename_lower = filename.lower()
        
        for ext in skip_extensions:
            if filename_lower.endswith(ext):
                return True
        
        for pattern in skip_patterns:
            if pattern in filename_lower:
                return True
        
        return False
    
    def _generate_detailed_summary(
        self,
        findings: List[Dict[str, Any]],
        pr_details: Dict[str, Any],
        custom_instructions: str
    ) -> str:
        """Generate comprehensive summary including agent thinking processes"""
        
        summary_parts = [
            "# AI Code Review - Deep Analysis Report",
            "",
            f"**PR #{pr_details['number']}: {pr_details['title']}**",
            f"**Repository**: {pr_details.get('base_branch', 'main')} ← {pr_details.get('head_branch', 'feature')}",
            f"**Author**: {pr_details['author']}",
            "",
            f"**Changes Summary:**",
            f"- Files changed: {pr_details['changed_files']}",
            f"- Lines added: {pr_details['additions']}",
            f"- Lines removed: {pr_details['deletions']}",
            ""
        ]
        
        if custom_instructions:
            summary_parts.extend([
                "**Custom Review Instructions:**",
                f"> {custom_instructions}",
                ""
            ])
        
        findings_with_issues = [f for f in findings if f.get("has_issues", False)]
        findings_without_issues = [f for f in findings if not f.get("has_issues", False)]
        
        if not findings_with_issues:
            summary_parts.extend([
                "---",
                "",
                "## All Clear",
                "",
                "All automated agents have analyzed the code and found no significant issues.",
                "The changes appear to be well-implemented across all review dimensions:",
                "",
                "- Logic & Correctness: No issues detected",
                "- Security: No vulnerabilities found",
                "- Performance: No concerns identified",
                "- Readability: Code meets quality standards",
                ""
            ])
        else:
            severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0, "none": 0}
            for finding in findings_with_issues:
                severity = finding.get("severity", "info")
                severity_counts[severity] = severity_counts.get(severity, 0) + 1
            
            summary_parts.extend([
                "---",
                "",
                "## Findings Overview",
                "",
                f"**Total Issues Found**: {len(findings_with_issues)} across {len(set(f['file'] for f in findings_with_issues))} files",
                ""
            ])
            
            if severity_counts["critical"] > 0:
                summary_parts.append(f"- Critical: {severity_counts['critical']}")
            if severity_counts["high"] > 0:
                summary_parts.append(f"- High: {severity_counts['high']}")
            if severity_counts["medium"] > 0:
                summary_parts.append(f"- Medium: {severity_counts['medium']}")
            if severity_counts["low"] > 0:
                summary_parts.append(f"- Low: {severity_counts['low']}")
            
            summary_parts.extend(["", "---", ""])
            
            by_file = {}
            for finding in findings_with_issues:
                file = finding.get("file", "unknown")
                if file not in by_file:
                    by_file[file] = []
                by_file[file].append(finding)
            
            agent_emojis = {
                "Logic & Correctness": "",
                "Security": "",
                "Performance": "",
                "Readability & Maintainability": ""
            }
            
            for file_path, file_findings in by_file.items():
                summary_parts.extend([
                    f"## File: `{file_path}`",
                    ""
                ])
                
                for finding in file_findings:
                    agent_type = finding.get("agent", "Unknown")
                    emoji = agent_emojis.get(agent_type, "")
                    severity = finding.get("severity", "info").upper()
                    
                    summary_parts.extend([
                        f"### {emoji} {agent_type} - [{severity}]",
                        ""
                    ])
                    
                    thinking = finding.get("thinking_process", "")
                    if thinking:
                        summary_parts.extend([
                            "**Agent's Thinking Process:**",
                            "",
                            thinking[:500] + ("..." if len(thinking) > 500 else ""),
                            ""
                        ])
                    
                    issues = finding.get("issues", [])
                    if issues:
                        summary_parts.extend(["**Issues Identified:**", ""])
                        for issue in issues[:5]:
                            desc = issue.get("description", "")
                            issue_sev = issue.get("severity", "MEDIUM")
                            summary_parts.append(f"- [{issue_sev}] {desc}")
                        if len(issues) > 5:
                            summary_parts.append(f"- ...and {len(issues) - 5} more")
                        summary_parts.append("")
                    
                    recommendations = finding.get("recommendations", [])
                    if recommendations:
                        summary_parts.extend(["**Recommendations:**", ""])
                        for rec in recommendations[:3]:
                            summary_parts.append(f"- {rec}")
                        if len(recommendations) > 3:
                            summary_parts.append(f"- ...and {len(recommendations) - 3} more")
                        summary_parts.append("")
                    
                    summary_parts.extend(["---", ""])
        
        all_positive = []
        for finding in findings:
            positives = finding.get("positive_observations", [])
            all_positive.extend(positives)
        
        if all_positive:
            summary_parts.extend([
                "## Positive Observations",
                "",
                "Good practices identified by the review agents:",
                ""
            ])
            for obs in all_positive[:5]:
                summary_parts.append(f"- {obs}")
            summary_parts.extend(["", "---", ""])
        
        summary_parts.extend([
            "",
            "---",
            "*Generated by AI PR Review Agent with LangChain-powered critical thinking*"
        ])
        
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
            await self.github_service.post_general_comment(
                owner, repo, pr_number, summary
            )
        except Exception as e:
            raise Exception(f"Failed to post review to GitHub: {str(e)}")
