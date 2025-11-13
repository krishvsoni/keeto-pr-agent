"""LangChain-powered PR review agents with critical thinking capabilities"""
from typing import Dict, Any, List, Optional
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from src.config import settings
import json
import re


class LangChainReviewAgent:
    """Base agent using LangChain for structured reasoning"""
    
    def __init__(self, agent_type: str, focus_areas: List[str]):
        self.agent_type = agent_type
        self.focus_areas = focus_areas
        
        self.llm = ChatOpenAI(
            model=settings.openrouter_model,
            temperature=0.3,  
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
            default_headers={
                "HTTP-Referer": "http://localhost:8000",
                "X-Title": f"PR Review Agent - {agent_type}"
            }
        )
        
        self.chain = self._create_analysis_chain()
    
    def _create_system_prompt(self) -> str:
        """Create the system prompt for this agent"""
        return f"""You are an expert code reviewer specializing in {self.agent_type} analysis.

Your role is to perform deep, critical analysis of code changes in pull requests.

Focus Areas: {', '.join(self.focus_areas)}

Analysis Methodology:
1. **Initial Assessment**: Quickly scan the changes to understand scope and intent
2. **Deep Dive**: Examine each significant change with critical thinking
3. **Pattern Recognition**: Identify anti-patterns, best practices violations, or improvements
4. **Impact Analysis**: Consider broader implications (performance, security, maintainability)
5. **Recommendations**: Provide specific, actionable feedback

Critical Thinking Process:
- Question assumptions in the code
- Consider edge cases and failure scenarios
- Think about long-term maintenance implications
- Evaluate alternatives that might be better
- Be thorough but fair - praise good practices too

Output Format:
Provide your analysis in the following structured format:

## Thinking Process
[Step-by-step reasoning about what you're analyzing and why]

## Issues Found
[List specific issues with severity levels: CRITICAL, HIGH, MEDIUM, LOW, INFO]

## Recommendations
[Actionable suggestions for improvement]

## Positive Observations
[Good practices worth highlighting]

Be specific, reference line numbers or code patterns when possible, and explain the "why" behind each finding."""

    def _create_analysis_chain(self):
        """Create the LangChain analysis chain"""
        system_prompt = SystemMessagePromptTemplate.from_template(
            self._create_system_prompt()
        )
        
        human_prompt = HumanMessagePromptTemplate.from_template(
            """Analyze the following code changes from a pull request.

**File**: {file_path}

**Custom Instructions** (if provided by user):
{custom_instructions}

**Code Diff**:
```diff
{code_diff}
```

**Additional Context**:
{context}

Perform a thorough {agent_type} analysis following the critical thinking process outlined in your instructions."""
        )
        
        chat_prompt = ChatPromptTemplate.from_messages([system_prompt, human_prompt])
        
        # Create the chain
        chain = chat_prompt | self.llm | StrOutputParser()
        
        return chain
    
    async def analyze(
        self,
        file_data: Dict[str, Any],
        custom_instructions: str = "",
        context: str = ""
    ) -> Dict[str, Any]:
        """
        Analyze code changes with critical thinking
        
        Args:
            file_data: File information including patch/diff
            custom_instructions: User-provided review instructions
            context: Additional context about the PR
            
        Returns:
            Structured analysis results
        """
        if not file_data.get("patch"):
            return {
                "agent": self.agent_type,
                "file": file_data["filename"],
                "analysis": "No code changes to review",
                "thinking_process": "",
                "issues": [],
                "recommendations": [],
                "positive_observations": [],
                "has_issues": False,
                "severity": "none"
            }
        
        try:
            # Prepare input for the chain
            chain_input = {
                "file_path": file_data["filename"],
                "code_diff": file_data["patch"],
                "custom_instructions": custom_instructions or "No specific instructions provided.",
                "context": context or "No additional context provided.",
                "agent_type": self.agent_type
            }
            
            # Run the analysis chain
            analysis_text = await self.chain.ainvoke(chain_input)
            
            # Parse the structured output
            parsed_result = self._parse_analysis(analysis_text, file_data["filename"])
            
            return parsed_result
            
        except Exception as e:
            return {
                "agent": self.agent_type,
                "file": file_data["filename"],
                "analysis": f"Error during analysis: {str(e)}",
                "thinking_process": "",
                "issues": [],
                "recommendations": [],
                "positive_observations": [],
                "has_issues": False,
                "severity": "none",
                "error": str(e)
            }
    
    def _parse_analysis(self, analysis_text: str, filename: str) -> Dict[str, Any]:
        """Parse the LLM's structured output"""
        
        # Extract sections using regex
        thinking_match = re.search(
            r'##\s*Thinking Process\s*\n(.*?)(?=##|\Z)',
            analysis_text,
            re.DOTALL | re.IGNORECASE
        )
        issues_match = re.search(
            r'##\s*Issues Found\s*\n(.*?)(?=##|\Z)',
            analysis_text,
            re.DOTALL | re.IGNORECASE
        )
        recommendations_match = re.search(
            r'##\s*Recommendations\s*\n(.*?)(?=##|\Z)',
            analysis_text,
            re.DOTALL | re.IGNORECASE
        )
        positive_match = re.search(
            r'##\s*Positive Observations\s*\n(.*?)(?=##|\Z)',
            analysis_text,
            re.DOTALL | re.IGNORECASE
        )
        
        thinking_process = thinking_match.group(1).strip() if thinking_match else ""
        issues_text = issues_match.group(1).strip() if issues_match else ""
        recommendations_text = recommendations_match.group(1).strip() if recommendations_match else ""
        positive_text = positive_match.group(1).strip() if positive_match else ""
        
        # Parse issues to determine severity
        issues = self._parse_issues(issues_text)
        severity = self._determine_severity(issues)
        
        return {
            "agent": self.agent_type,
            "file": filename,
            "analysis": analysis_text,
            "thinking_process": thinking_process,
            "issues": issues,
            "recommendations": self._parse_list_items(recommendations_text),
            "positive_observations": self._parse_list_items(positive_text),
            "has_issues": len(issues) > 0,
            "severity": severity
        }
    
    def _parse_issues(self, issues_text: str) -> List[Dict[str, Any]]:
        """Parse issues from text"""
        issues = []
        
        # Look for lines that start with - or * or numbers
        lines = issues_text.split('\n')
        current_issue = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Check for severity markers
            severity_match = re.search(
                r'\[?(CRITICAL|HIGH|MEDIUM|LOW|INFO)\]?',
                line,
                re.IGNORECASE
            )
            
            if re.match(r'^[-*•]\s+', line) or re.match(r'^\d+\.\s+', line):
                # Start of new issue
                issue_text = re.sub(r'^[-*•\d.]\s+', '', line)
                current_issue = {
                    "description": issue_text,
                    "severity": severity_match.group(1).upper() if severity_match else "MEDIUM"
                }
                issues.append(current_issue)
            elif current_issue and line:
                # Continuation of current issue
                current_issue["description"] += " " + line
        
        return issues
    
    def _parse_list_items(self, text: str) -> List[str]:
        """Parse list items from text"""
        items = []
        lines = text.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Remove list markers
            line = re.sub(r'^[-*•\d.]\s+', '', line)
            if line:
                items.append(line)
        
        return items
    
    def _determine_severity(self, issues: List[Dict[str, Any]]) -> str:
        """Determine overall severity from issues list"""
        if not issues:
            return "none"
        
        severity_order = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]
        
        for severity in severity_order:
            if any(issue.get("severity") == severity for issue in issues):
                return severity.lower()
        
        return "low"


class LogicReviewAgent(LangChainReviewAgent):
    """Agent specialized in logic and correctness analysis"""
    
    def __init__(self):
        super().__init__(
            agent_type="Logic & Correctness",
            focus_areas=[
                "Algorithmic correctness",
                "Edge case handling",
                "Null/undefined checks",
                "Loop invariants",
                "Conditional logic",
                "Error handling",
                "Race conditions",
                "Data consistency"
            ]
        )


class SecurityReviewAgent(LangChainReviewAgent):
    """Agent specialized in security analysis"""
    
    def __init__(self):
        super().__init__(
            agent_type="Security",
            focus_areas=[
                "SQL injection vulnerabilities",
                "XSS (Cross-Site Scripting)",
                "Authentication/Authorization",
                "Input validation",
                "Data sanitization",
                "Sensitive data exposure",
                "Cryptography usage",
                "Dependency vulnerabilities",
                "CSRF protection",
                "API security"
            ]
        )


class PerformanceReviewAgent(LangChainReviewAgent):
    """Agent specialized in performance analysis"""
    
    def __init__(self):
        super().__init__(
            agent_type="Performance",
            focus_areas=[
                "Time complexity (O-notation)",
                "Space complexity",
                "Database query optimization",
                "N+1 query problems",
                "Caching opportunities",
                "Memory leaks",
                "Unnecessary computations",
                "API call efficiency",
                "Resource management",
                "Algorithmic improvements"
            ]
        )


class ReadabilityReviewAgent(LangChainReviewAgent):
    """Agent specialized in code quality and readability"""
    
    def __init__(self):
        super().__init__(
            agent_type="Readability & Maintainability",
            focus_areas=[
                "Code clarity",
                "Naming conventions",
                "Function/method length",
                "Code duplication",
                "Comments and documentation",
                "Design patterns",
                "SOLID principles",
                "Code organization",
                "Type safety",
                "Test coverage considerations"
            ]
        )
