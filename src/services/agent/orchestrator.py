"""Orchestrator agent that coordinates all review agents."""
from typing import Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

from .security_agent import SecurityAgent
from .logic_agent import LogicAgent
from .performance_agent import PerformanceAgent
from .readability_agent import ReadabilityAgent
from .test_coverage_agent import TestCoverageAgent


class OrchestratorAgent:
    """
    Orchestrator that coordinates multiple specialized review agents.
    Each agent analyzes the PR independently and returns JSON results.
    """
    
    def __init__(self):
        """Initialize all specialized agents."""
        self.agents = {
            "security": SecurityAgent(),
            "logic": LogicAgent(),
            "performance": PerformanceAgent(),
            "readability": ReadabilityAgent(),
            "test_coverage": TestCoverageAgent()
        }
    
    def review_pr(
        self, 
        pr_diff: str, 
        pr_info: Dict[str, Any],
        selected_agents: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Orchestrate a complete PR review using multiple agents.
        
        Args:
            pr_diff: The git diff of the PR
            pr_info: Metadata about the PR (title, description, url, etc.)
            selected_agents: List of agent names to run. If None, runs all agents.
            
        Returns:
            Dict containing aggregated review results from all agents
        """
        start_time = time.time()
        
        # Determine which agents to run
        agents_to_run = selected_agents if selected_agents else list(self.agents.keys())
        
        # Validate agent names
        invalid_agents = [a for a in agents_to_run if a not in self.agents]
        if invalid_agents:
            return {
                "error": f"Invalid agent names: {invalid_agents}",
                "valid_agents": list(self.agents.keys())
            }
        
        # Run agents in parallel
        results = {}
        errors = {}
        
        with ThreadPoolExecutor(max_workers=len(agents_to_run)) as executor:
            # Submit all agent tasks
            future_to_agent = {
                executor.submit(
                    self.agents[agent_name].analyze, 
                    pr_diff, 
                    pr_info
                ): agent_name
                for agent_name in agents_to_run
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_agent):
                agent_name = future_to_agent[future]
                try:
                    result = future.result(timeout=60)  # 60 second timeout per agent
                    results[agent_name] = result
                except Exception as e:
                    errors[agent_name] = str(e)
                    results[agent_name] = {
                        "agent": agent_name,
                        "severity": "info",
                        "issues": [],
                        "summary": f"Agent failed: {str(e)}",
                        "score": 0,
                        "error": str(e)
                    }
        
        # Aggregate results
        end_time = time.time()
        
        return self._aggregate_results(results, pr_info, start_time, end_time, errors)
    
    def _aggregate_results(
        self, 
        results: Dict[str, Dict[str, Any]], 
        pr_info: Dict[str, Any],
        start_time: float,
        end_time: float,
        errors: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Aggregate all agent results into a comprehensive report.
        
        Args:
            results: Dict mapping agent names to their results
            pr_info: Original PR information
            start_time: Review start timestamp
            end_time: Review end timestamp
            errors: Any errors that occurred during review
            
        Returns:
            Comprehensive review report
        """
        # Collect all issues across agents
        all_issues = []
        for agent_name, result in results.items():
            issues = result.get("issues", [])
            for issue in issues:
                issue["agent"] = agent_name
                all_issues.append(issue)
        
        # Sort issues by severity
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
        all_issues.sort(key=lambda x: severity_order.get(x.get("severity", "info"), 4))
        
        # Count issues by severity
        severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
        for issue in all_issues:
            severity = issue.get("severity", "info")
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
        
        # Calculate overall score (weighted average)
        scores = [result.get("score", 0) for result in results.values() if result.get("score")]
        overall_score = sum(scores) / len(scores) if scores else 0
        
        # Determine overall recommendation
        critical_count = severity_counts["critical"]
        high_count = severity_counts["high"]
        
        if critical_count > 0:
            recommendation = "BLOCK - Critical issues must be resolved"
        elif high_count > 3:
            recommendation = "REQUEST CHANGES - Multiple high-severity issues found"
        elif high_count > 0:
            recommendation = "COMMENT - Address high-severity issues"
        elif severity_counts["medium"] > 5:
            recommendation = "COMMENT - Several improvements suggested"
        else:
            recommendation = "APPROVE - Looks good!"
        
        return {
            "pr_info": pr_info,
            "overall_score": round(overall_score, 2),
            "recommendation": recommendation,
            "summary": {
                "total_issues": len(all_issues),
                "by_severity": severity_counts,
                "agents_run": list(results.keys()),
                "review_time_seconds": round(end_time - start_time, 2)
            },
            "agent_results": results,
            "issues": all_issues,
            "errors": errors if errors else None,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(end_time))
        }
    
    def get_available_agents(self) -> List[str]:
        """Return list of available agent names."""
        return list(self.agents.keys())
