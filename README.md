# Keeto PR Review Agent

Automated Pull Request review system powered by multi-agent LLM analysis.

## How It Works

1. GitHub webhook triggers on new PR
2. System fetches PR diff and files
3. Specialized agents analyze the code:
   - Logic Agent - Reviews code correctness and business logic
   - Readability Agent - Checks code clarity and maintainability
   - Performance Agent - Identifies optimization opportunities
   - Security Agent - Detects vulnerabilities and security issues
   - Test Coverage Agent - Evaluates test completeness and quality
4. Orchestrator agent combines all feedback
5. Review posted as PR comment

## Docker Setup

```bash
docker pull krishsoni/keeto:latest
docker run -p 8000:8000 --env-file .env krishsoni/keeto:latest
```

Docker Hub: https://hub.docker.com/r/krishsoni/keeto

## Configuration

Create `.env` file:

```
GITHUB_TOKEN=your_token
OPENROUTER_API_KEY=your_key
```

[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/krishvsoni/keeto-pr-agent)