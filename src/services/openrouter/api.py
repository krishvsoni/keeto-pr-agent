import httpx
from typing import Dict, Any, List, Optional
from src.config import settings


class OpenRouterService:
    """Service for interacting with OpenRouter API (OpenAI-compatible)"""
    
    def __init__(self):
        self.base_url = settings.openrouter_base_url
        self.api_key = settings.openrouter_api_key
        self.model = settings.openrouter_model
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:8000",
            "X-Title": "PR Review Agent"
        }
    
    async def generate_completion(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> str:
        """Generate completion using OpenRouter API"""
        try:
            messages = []
            
            if system_prompt:
                messages.append({
                    "role": "system",
                    "content": system_prompt
                })
            
            messages.append({
                "role": "user",
                "content": prompt
            })
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=self.headers,
                    json={
                        "model": self.model,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens
                    }
                )
                
                response.raise_for_status()
                data = response.json()
                
                return data["choices"][0]["message"]["content"]
        
        except Exception as e:
            raise Exception(f"OpenRouter API error: {str(e)}")
    
    async def analyze_code(
        self,
        code_diff: str,
        file_path: str,
        analysis_type: str,
        context: Optional[str] = None
    ) -> Dict[str, Any]:
        """Analyze code using LLM with specific focus"""
        
        system_prompts = {
            "logic": """You are an expert code reviewer focusing on logic and correctness.
Analyze the code for:
- Logic errors and bugs
- Edge cases not handled
- Incorrect algorithms
- Potential runtime errors
- Business logic issues""",
            
            "readability": """You are an expert code reviewer focusing on code readability and maintainability.
Analyze the code for:
- Code clarity and naming conventions
- Code structure and organization
- Documentation and comments
- Consistency with best practices
- Complexity that could be simplified""",
            
            "performance": """You are an expert code reviewer focusing on performance optimization.
Analyze the code for:
- Inefficient algorithms (O(n²) where O(n) possible)
- Unnecessary loops or computations
- Memory leaks or excessive memory usage
- Database query optimization
- Caching opportunities""",
            
            "security": """You are an expert code reviewer focusing on security vulnerabilities.
Analyze the code for:
- SQL injection vulnerabilities
- XSS vulnerabilities
- Authentication/authorization issues
- Sensitive data exposure
- Input validation issues
- Insecure dependencies"""
        }
        
        system_prompt = system_prompts.get(analysis_type, system_prompts["logic"])
        
        user_prompt = f"""File: {file_path}

Code Changes:
```
{code_diff}
```

{f"Additional Context:\n{context}\n" if context else ""}

Provide a structured review with:
1. Issues found (be specific with line numbers if visible)
2. Severity (Critical/High/Medium/Low)
3. Recommendation for fixing

Format your response as clear, actionable feedback. If no issues found, state "No issues found."
"""
        
        try:
            response = await self.generate_completion(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.3,
                max_tokens=1500
            )
            
            return {
                "analysis_type": analysis_type,
                "file_path": file_path,
                "findings": response,
                "has_issues": "no issues found" not in response.lower()
            }
        
        except Exception as e:
            return {
                "analysis_type": analysis_type,
                "file_path": file_path,
                "findings": f"Analysis failed: {str(e)}",
                "has_issues": False,
                "error": str(e)
            }
