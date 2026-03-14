# Agent Architecture

## Overview

This document describes the architecture of the agent CLI (`agent.py`) that connects to an LLM and returns structured JSON answers.

## LLM Provider

**Provider:** OpenRouter

**Model:** `meta-llama/llama-3.3-70b-instruct:free`

**Why this provider:**

- Free tier available (50 requests/day)
- No credit card required
- OpenAI-compatible API
- Strong tool calling capabilities (for future tasks)

> **Note:** Free models may be temporarily unavailable due to rate limits. For production use, consider upgrading to a paid tier or switching to Qwen Code API.

## Configuration

The agent reads configuration from `.env.agent.secret`:

| Variable | Description | Example |
|----------|-------------|---------|
| `LLM_API_KEY` | API key for authentication | `your-api-key` |
| `LLM_API_BASE` | Base URL of the API endpoint | `http://localhost:8080/v1` |
| `LLM_MODEL` | Model name to use | `qwen3-coder-plus` |

## How It Works

### Input

```bash
uv run agent.py "What does REST stand for?"
```

The question is passed as the first command-line argument.

### Processing Flow

1. **Parse arguments** - Extract question from `sys.argv[1]`
2. **Load environment** - Read `.env.agent.secret` for API credentials
3. **Validate** - Ensure all required env vars are present
4. **Call LLM** - POST to `{LLM_API_BASE}/chat/completions`
5. **Parse response** - Extract `choices[0].message.content`
6. **Output JSON** - Print result to stdout

### Output

```json
{"answer": "Representational State Transfer.", "tool_calls": []}
```

| Field | Type | Description |
|-------|------|-------------|
| `answer` | string | The LLM's response to the question |
| `tool_calls` | array | Empty for Task 1 (populated in Task 2) |

### Error Handling

- Missing CLI argument → usage message to stderr, exit 1
- Missing `.env.agent.secret` → error to stderr, exit 1
- HTTP failure → error to stderr, exit 1
- Invalid response → error to stderr, exit 1
- Timeout > 60 seconds → process terminates

## Logging

All debug output goes to **stderr**:

- Question being asked
- API endpoint being called
- Model being used
- Status updates

Only the final JSON result goes to **stdout**.

## Running the Agent

```bash
# Set up environment
cp .env.agent.example .env.agent.secret
# Edit .env.agent.secret with your credentials

# Run the agent
uv run agent.py "Your question here"
```

## Testing

Run the regression test:

```bash
uv run pytest backend/tests/e2e/test_agent_task1.py -v
```

The test verifies:

- Exit code is 0
- Output is valid JSON
- `answer` field exists and is non-empty
- `tool_calls` field exists and is an empty array

## Future Work (Tasks 2-3)

- Add tool definitions (search, query_api, etc.)
- Implement agentic loop for multi-step reasoning
- Populate `tool_calls` array with tool invocations
- Expand system prompt with domain knowledge
