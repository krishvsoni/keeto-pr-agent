## Keeto PR Review Agent

An automated Pull Request review system powered by multi-agent LLM analysis. This system analyzes code changes in GitHub PRs and provides structured, actionable feedback on logic, readability, performance, and security.



Just open http://localhost:8000 in your browser and start chatting with the AI reviewer. No curl commands needed!

Features:
- Chat-like interface for natural interaction
- Simple form: enter owner, repo, PR number, and optional issue context
- Beautiful gradient design with real-time feedback
- Visual stats and detailed findings
- Option to post comments directly to GitHub

See [CHAT_GUIDE.md](CHAT_GUIDE.md) for detailed usage instructions.

## Features

### Core Capabilities
- **Multi-Agent Analysis**: 4 specialized agents analyze different aspects
  - **Logic Agent**: Detects bugs, edge cases, and logic errors
  - **Readability Agent**: Reviews code clarity and maintainability
  - **Performance Agent**: Identifies optimization opportunities
  - **Security Agent**: Finds vulnerabilities and security issues

### Integration Features
- **GitHub API Integration**: Fetch PR diffs, post review comments
- **OpenRouter LLM Integration**: AI-powered code analysis
- **Webhook Support**: Automatic reviews on PR events
- **Manual Review API**: Trigger reviews on-demand

### Backend Stack
- **FastAPI**: High-performance async API framework
- **Python 3.10+**: Modern Python features
- **PyGithub**: GitHub API wrapper
- **OpenRouter**: Multi-LLM access via OpenAI-compatible API
- **Pydantic**: Data validation and settings management

---

##  Quick Start

### 1. Prerequisites
- Python 3.10 or higher
- GitHub Personal Access Token
- OpenRouter API Key

### 2. Installation

```bash
# Clone or navigate to project
cd keeto

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configuration

Create `.env` file from template:
```bash
cp .env.example .env
```

Edit `.env` with your credentials:
```env
# GitHub Configuration
GITHUB_TOKEN=ghp_your_github_token_here
GITHUB_WEBHOOK_SECRET=your_webhook_secret  # Optional

# OpenRouter Configuration
OPENROUTER_API_KEY=sk-or-v1-your_key_here

# Server Configuration
PORT=8000
HOST=0.0.0.0
```

#### Getting API Keys:

**GitHub Token:**
1. Go to GitHub Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Generate new token with scopes: `repo` (full control)
3. Copy token to `.env`

**OpenRouter Key:**
1. Visit https://openrouter.ai/
2. Sign up/Login
3. Go to Keys section
4. Create new API key
5. Copy to `.env`

### 4. Run the Server

```bash
# From project root
python -m src.main
```

Server will start at: `http://localhost:8000`

**Open your browser and go to http://localhost:8000 to use the chat interface!**

Or use the API endpoints (see below).

---

##  Using the Chat Interface

The easiest way to use the PR review agent!

1. **Open** http://localhost:8000 in your browser
2. **Fill in** the form:
   - Repository Owner (e.g., `facebook`)
   - Repository Name (e.g., `react`)
   - PR Number (e.g., `123`)
   - Issue Being Addressed (optional, e.g., "Fixes login bug")
   - Check "Post comments to GitHub" if you want results posted
3. **Click** "Analyze PR"
4. **View** results in beautiful chat format!





##  Architecture

```
┌─────────────────┐
│   GitHub PR     │
│   (Webhook)     │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────┐
│   FastAPI Backend           │
│   (http://localhost:8000)   │
└─────────┬───────────────────┘
          │
          ▼
┌─────────────────────────────┐
│   Agent Orchestrator        │
│   - Coordinates agents      │
│   - Manages workflow        │
└─────────┬───────────────────┘
          │
          ├──────────┬──────────┬──────────┐
          ▼          ▼          ▼          ▼
    ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐
    │ Logic   │ │Readable │ │Perform  │ │Security │
    │ Agent   │ │ Agent   │ │ Agent   │ │ Agent   │
    └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘
         │           │           │           │
         └───────────┴───────────┴───────────┘
                     │
                     ▼
         ┌─────────────────────┐
         │  OpenRouter API     │
         │  (LLM Analysis)     │
         └─────────────────────┘
```

### Workflow
1. **PR Event** → Webhook triggers or manual API call
2. **Fetch Data** → Get PR details and diffs from GitHub
3. **Multi-Agent Analysis** → Each agent analyzes code independently
4. **Aggregate Results** → Combine findings into structured report
5. **Post Comments** → Send feedback back to GitHub PR

---

## Project Structure

```
keeto/
├── src/
│   ├── main.py                 # FastAPI application & endpoints
│   ├── config.py               # Configuration & settings
│   ├── models.py               # Pydantic models
│   ├── services/
│   │   ├── agent/
│   │   │   ├── agent.py        # Review agent classes
│   │   │   └── orchestrator.py # Multi-agent coordinator
│   │   ├── github/
│   │   │   └── api.py          # GitHub API client
│   │   └── openrouter/
│   │       └── api.py          # OpenRouter LLM client
├── requirements.txt            # Python dependencies
├── .env.example               # Environment template
└── README.md                  # This file
```

---

##  Configuration Options

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `GITHUB_TOKEN` | GitHub personal access token | - | ✅ |
| `GITHUB_WEBHOOK_SECRET` | Webhook signature secret | "" | ❌ |
| `OPENROUTER_API_KEY` | OpenRouter API key | - | ✅ |
| `OPENROUTER_BASE_URL` | OpenRouter API endpoint | `https://openrouter.ai/api/v1` | ❌ |
| `OPENROUTER_MODEL` | LLM model to use | `meta-llama/llama-3.1-8b-instruct:free` | ❌ |
| `HOST` | Server host | `0.0.0.0` | ❌ |
| `PORT` | Server port | `8000` | ❌ |

### Available LLM Models
OpenRouter supports many models. Free options:
- `meta-llama/llama-3.1-8b-instruct:free`
- `meta-llama/llama-3.1-70b-instruct:free`
- `google/gemini-flash-1.5:free`

See https://openrouter.ai/models for full list.

---

## 🧪 Testing the System

### Test Manual Review
```bash
# Review a real PR
curl -X POST http://localhost:8000/review \
  -H "Content-Type: application/json" \
  -d '{
    "owner": "microsoft",
    "repo": "vscode",
    "pr_number": 1,
    "post_comments": false
  }'
```

### Test Diff Analysis
```python
# test_review.py
import requests

diff = """
@@ -1,5 +1,8 @@
 def process_user_input(user_id):
-    query = f"SELECT * FROM users WHERE id = {user_id}"
-    return db.execute(query)
+    # Fixed SQL injection vulnerability
+    query = "SELECT * FROM users WHERE id = ?"
+    return db.execute(query, (user_id,))
"""

response = requests.post(
    "http://localhost:8000/review-diff",
    json={
        "file_path": "api/users.py",
        "code_diff": diff,
        "analysis_types": ["security", "logic"]
    }
)

print(response.json())
```

---

##  Use Cases

### 1. Automated PR Review on Push
- Configure webhook
- Every new PR gets automatic review
- Comments posted directly to GitHub

### 2. Pre-commit Local Review
- Review changes before pushing
- Use `/review-diff` endpoint
- Catch issues early

### 3. CI/CD Integration
- Add to GitHub Actions workflow
- Block merges on critical findings
- Enforce code quality standards

---

##  Development

### Running in Development
```bash
# With auto-reload
python -m src.main

# Or with uvicorn directly
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

### API Documentation
Once running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

---

##  Troubleshooting

### Common Issues

**"Module not found" error:**
```bash
# Ensure you're in project root and venv is activated
pip install -r requirements.txt
```

**"Invalid GitHub token":**
- Check token has `repo` scope
- Token should start with `ghp_` or `github_pat_`

**"OpenRouter API error":**
- Verify API key is correct
- Check you have credits (free models don't need credits)
- Ensure model name is valid

**Webhook not triggering:**
- Check webhook URL is publicly accessible (use ngrok for local testing)
- Verify webhook secret matches `.env`
- Check GitHub webhook delivery logs

---

## Future Enhancements

- [ ] Add test coverage analysis
- [ ] Support for multiple LLM providers
- [ ] Custom review rules configuration
- [ ] Review history and analytics
- [ ] Support for other version control systems
- [ ] Configurable severity thresholds




