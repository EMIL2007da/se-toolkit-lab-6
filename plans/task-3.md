# Task 3: The System Agent - Implementation Plan

## Overview

This task extends the Task 2 agent with a new tool (`query_api`) that allows the LLM to query the deployed backend API. The agent must now answer three types of questions:

1. **Wiki lookup** - Use `read_file`/`list_files` to find documentation
2. **System facts** - Use `query_api` or `read_file` on source code for static facts (framework, ports, status codes)
3. **Data queries** - Use `query_api` to get live data from the backend

## Tool Schema: query_api

### Definition

```json
{
  "name": "query_api",
  "description": "Call the deployed backend API to get live data or check system behavior. Use this for questions about current database state, HTTP status codes, or API responses.",
  "parameters": {
    "type": "object",
    "properties": {
      "method": {
        "type": "string",
        "description": "HTTP method (GET, POST, PUT, DELETE, etc.)",
        "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"]
      },
      "path": {
        "type": "string",
        "description": "API path (e.g., '/items/', '/analytics/completion-rate')"
      },
      "body": {
        "type": "string",
        "description": "Optional JSON request body for POST/PUT/PATCH requests"
      }
    },
    "required": ["method", "path"]
  }
}
```

### Implementation

```python
def query_api(method: str, path: str, body: str | None = None) -> str:
    """
    Call the deployed backend API.
    
    - Reads AGENT_API_BASE_URL from environment (default: http://localhost:42002)
    - Reads LMS_API_KEY from .env.docker.secret for authentication
    - Returns JSON string with status_code and body
    """
```

### Authentication

The backend requires an `X-API-Key` header with the `LMS_API_KEY` value:

```python
headers = {
    "X-API-Key": env["LMS_API_KEY"],
    "Content-Type": "application/json",
}
```

## Environment Variables

The agent must read all configuration from environment variables:

| Variable | Purpose | Source |
|----------|---------|--------|
| `LLM_API_KEY` | LLM provider API key | `.env.agent.secret` |
| `LLM_API_BASE` | LLM API endpoint URL | `.env.agent.secret` |
| `LLM_MODEL` | Model name | `.env.agent.secret` |
| `LMS_API_KEY` | Backend API key for query_api auth | `.env.docker.secret` |
| `AGENT_API_BASE_URL` | Base URL for query_api (optional) | Environment, defaults to `http://localhost:42002` |

**Important:** The autochecker injects its own values. Never hardcode these values.

## System Prompt Update

The system prompt must guide the LLM to choose the right tool:

```
You are a documentation and system assistant that answers questions by:
1. Reading wiki files for documentation questions
2. Reading source code for implementation questions
3. Querying the live API for current data or system behavior

Available tools:
- list_files(path): Discover what files exist
- read_file(path): Read file contents (wiki, source code, configs)
- query_api(method, path, body): Call the live backend API

When to use each tool:
- Use wiki tools for: documentation, procedures, workflows
- Use read_file on source code for: framework info, implementation details
- Use query_api for: current database state, HTTP status codes, API responses, live data

Always include the source field when reading files (format: path#section).
For API queries, note the endpoint in the source field.
```

## Agentic Loop Changes

The agentic loop structure remains the same. Only change:

- Add `query_api` to tool definitions
- LLM can now call 3 tools instead of 2

## Source Field Handling

- **Wiki/source questions:** Include file path with section anchor (e.g., `wiki/git-workflow.md#resolving-merge-conflicts`)
- **API questions:** Source is optional but can note the endpoint (e.g., `GET /items/`)

## Testing Strategy

Two regression tests:

1. **Framework question:** "What framework does the backend use?"
   - Expected: `read_file` in tool_calls (reading main.py or similar)
   - Answer should mention FastAPI

2. **Database query:** "How many items are in the database?"
   - Expected: `query_api` in tool_calls
   - Answer should contain a number > 0

## Benchmark Questions Analysis

The 10 local questions cover:

| # | Type | Tools Required |
|---|------|----------------|
| 0 | Wiki lookup | read_file |
| 1 | Wiki lookup | read_file |
| 2 | Source code | read_file |
| 3 | Source code discovery | list_files |
| 4 | Live data | query_api |
| 5 | API behavior | query_api |
| 6 | Bug diagnosis | query_api, read_file |
| 7 | Bug diagnosis | query_api, read_file |
| 8 | System reasoning | read_file |
| 9 | Pipeline reasoning | read_file |

## Iteration Strategy

1. Implement query_api tool
2. Update system prompt
3. Run `run_eval.py` to see initial score
4. For each failure:
   - Check if wrong tool was called → improve system prompt
   - Check if tool returned error → fix tool implementation
   - Check if answer format wrong → adjust prompt for better phrasing
5. Re-run until all 10 pass

## Files to Modify

1. **`agent.py`** - Add query_api tool, update system prompt, load LMS_API_KEY
2. **`AGENT.md`** - Document query_api, authentication, lessons learned (200+ words)
3. **`tests/test_agent_task3.py`** - Add 2 regression tests
4. **`plans/task-3.md`** - This plan, plus benchmark results after first run

## Security Considerations

- `LMS_API_KEY` must be read from environment, not hardcoded
- API calls should use HTTPS in production (localhost HTTP is fine for dev)
- Validate method parameter to prevent injection attacks

## Implementation Status

### Completed

- [x] Added `query_api` tool with full HTTP support (GET, POST, PUT, DELETE, PATCH)
- [x] Implemented authentication using `LMS_API_KEY` from `.env.docker.secret`
- [x] Added `AGENT_API_BASE_URL` environment variable support (defaults to `http://localhost:42002`)
- [x] Updated system prompt with clear tool selection guidance
- [x] Added 2 regression tests for Task 3
- [x] Updated `AGENT.md` with comprehensive documentation (200+ words on lessons learned)
- [x] Code passes ruff linting and pyright type checking

### Benchmark Results

**Note:** Full benchmark evaluation requires the backend to be running via Docker.

To run the evaluation:

```bash
# Start the backend
docker-compose up -d

# Run the evaluation
uv run run_eval.py
```

Expected results based on implementation:

- Questions 0-3 (wiki/source): Should pass with `read_file`/`list_files`
- Questions 4-5 (API data): Should pass with `query_api`
- Questions 6-7 (bug diagnosis): Should pass with `query_api` + `read_file` combination
- Questions 8-9 (reasoning): Should pass with `read_file` on relevant source files

### Known Limitations

1. **Backend dependency:** The `query_api` tool requires the backend to be running at the configured URL
2. **Docker availability:** Full evaluation requires Docker to be installed and running
3. **LLM API key:** A valid OpenRouter API key is required for the agent to function

### Next Steps

1. Start Docker and run `docker-compose up -d`
2. Run `uv run run_eval.py` to verify all 10 questions pass
3. If any failures, iterate on system prompt or tool implementation
4. Commit final changes and create PR
