"""Base agent class for code review agents."""
from abc import ABC, abstractmethod
from typing import Dict, Any, List
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
import json


class BaseReviewAgent(ABC):
    """Abstract base class for all review agents."""
    
    def __init__(self, model_name: str = "openai/gpt-4o-mini", temperature: float = 0.2):
        """Initialize the base agent with LLM configuration."""
        self.model_name = model_name
        self.temperature = temperature
        self.llm = None
        self._initialize_llm()
    
    def _initialize_llm(self):
        """Initialize the LLM through OpenRouter."""
        from src.config import get_settings
        settings = get_settings()
        
        self.llm = ChatOpenAI(
            model=self.model_name,
            temperature=self.temperature,
            openai_api_key=settings.OPENROUTER_API_KEY,
            openai_api_base="https://openrouter.ai/api/v1"
        )
    
    @abstractmethod
    def get_system_prompt(self) -> str:
        """Return the system prompt for this agent."""
        pass
    
    @abstractmethod
    def get_agent_name(self) -> str:
        """Return the name of this agent."""
        pass
    
    def analyze(self, pr_diff: str, pr_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze the PR diff and return structured feedback.
        
        Args:
            pr_diff: The git diff of the PR
            pr_info: Metadata about the PR (title, description, etc.)
            
        Returns:
            Dict with analysis results in JSON format
        """
        # Create prompt template
        prompt = ChatPromptTemplate.from_messages([
            ("system", self.get_system_prompt()),
            ("user", """Analyze the following Pull Request:

PR Title: {title}
PR Description: {description}

Diff:
{diff}

Provide your analysis as JSON with the following structure:
{{
    "severity": "critical|high|medium|low|info",
    "issues": [
        {{
            "file": "filename",
            "line": line_number,
            "severity": "critical|high|medium|low|info",
            "title": "brief title",
            "description": "detailed description",
            "suggestion": "recommended fix with explanation",
            "suggested_code": "complete corrected code line or block that should replace the problematic code"
        }}
    ],
    "summary": "overall summary of findings",
    "score": 0-100
}}

IMPORTANT: For each issue, provide the complete corrected code in the "suggested_code" field. This should be the exact code that would replace the problematic line(s), ready to copy-paste.""")
        ])
        
        # Create chain with JSON parser
        parser = JsonOutputParser()
        chain = prompt | self.llm | parser
        
        try:
            result = chain.invoke({
                "title": pr_info.get("title", "N/A"),
                "description": pr_info.get("description", "N/A"),
                "diff": pr_diff[:15000]  # Limit diff size to avoid token limits
            })
            
            # Add agent metadata
            result["agent"] = self.get_agent_name()
            return result
            
        except Exception as e:
            return {
                "agent": self.get_agent_name(),
                "severity": "info",
                "issues": [],
                "summary": f"Analysis failed: {str(e)}",
                "score": 0,
                "error": str(e)
            }
