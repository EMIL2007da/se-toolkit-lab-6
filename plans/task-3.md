# Task 3: The System Agent - Implementation Plan

## Overview
This task extends the Task 2 documentation agent with a new `query_api` tool to answer questions about the live system.

## Implementation Plan

### 1. Tool Definition (`query_api`)
- **Name**: `query_api`
- **Parameters**:
  - `method` (string, required): HTTP method (GET, POST, PUT, DELETE, PATCH)
  - `path` (string, required): API endpoint path (e.g., `/items/`, `/analytics/completion-rate`)
  - `body` (string, optional): JSON request body for POST/PUT/PATCH
- **Returns**: JSON string with `status_code` and `body`
- **Authentication**: Uses `LMS_API_KEY` from `.env.docker.secret`

### 2. Environment Variables
The agent reads configuration from environment variables:
- `LLM_API_KEY`, `LLM_API_BASE`, `LLM_MODEL` - from `.env.agent.secret`
- `LMS_API_KEY` - from `.env.docker.secret` (for API authentication)
- `AGENT_API_BASE_URL` - optional, defaults to `http://localhost:42002`

### 3. System Prompt Updates
Updated the system prompt to guide the LLM on when to use each tool:
- `list_files`/`read_file` - for documentation, source code, configuration
- `query_api` - for live data, database state, HTTP status codes, API behavior

### 4. Key Code Changes
- Added `query_api()` function with HTTP client using `urllib`
- Added `load_docker_env()` to load LMS_API_KEY
- Added `get_api_base_url()` for configurable API endpoint
- Fixed tool call handling: added assistant message to conversation history before tool results

## Benchmark Diagnosis

### Initial Run
```
uv run run_eval.py
```

### Expected Failures and Fixes

| Issue | Cause | Fix |
|-------|-------|-----|
| Agent doesn't call query_api | System prompt unclear | Clarify when to use query_api vs read_file |
| API returns 401 | Missing LMS_API_KEY | Ensure .env.docker.secret exists |
| Tool result format error | Missing assistant message in history | Add `messages.append(message)` before tool results |
| Agent loops on list_files | LLM doesn't know wiki directory exists | Improve system prompt with examples |

## Iteration Strategy
1. Run `run_eval.py` to identify failures
2. Check agent output for tool usage patterns
3. Fix system prompt or tool implementation
4. Re-run tests until all 10 pass

## Acceptance Criteria Checklist
- [ ] `plans/task-3.md` exists with implementation plan
- [ ] `agent.py` defines `query_api` as function-calling schema
- [ ] `query_api` authenticates with `LMS_API_KEY`
- [ ] Agent reads all LLM config from environment variables
- [ ] Agent reads `AGENT_API_BASE_URL` (defaults to localhost:42002)
- [ ] Agent answers static system questions correctly
- [ ] Agent answers data-dependent questions
- [ ] `run_eval.py` passes all 10 local questions
- [ ] `AGENT.md` documents final architecture (200+ words)
- [ ] 2 tool-calling regression tests exist and pass
- [ ] Git workflow completed (issue, branch, PR, approval, merge)
