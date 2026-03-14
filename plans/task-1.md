# Task 1: Call an LLM from Code

## Implementation Plan

### LLM Provider and Model

**Provider:** OpenRouter

**Model:** `meta-llama/llama-3.3-70b-instruct:free`

**Rationale:**

- Free tier (50 requests/day)
- No credit card required
- OpenAI-compatible API
- Strong tool calling capabilities (needed for future tasks)

### Architecture

The agent will have the following components:

1. **Environment Configuration** (`.env.agent.secret`)
   - `LLM_API_KEY` - API key for authentication
   - `LLM_API_BASE` - Base URL of the OpenAI-compatible API endpoint
   - `LLM_MODEL` - Model name to use

2. **Command-Line Interface** (`agent.py`)
   - Parse the question from `sys.argv[1]`
   - Load environment variables from `.env.agent.secret`
   - Make HTTP POST request to `/v1/chat/completions`
   - Parse the LLM response
   - Output JSON to stdout, debug info to stderr

3. **API Communication**
   - Use `httpx` (already in project dependencies) for async HTTP requests
   - OpenAI-compatible request format:

     ```json
     {
       "model": "qwen3-coder-plus",
       "messages": [{"role": "user", "content": "<question>"}]
     }
     ```

   - Parse response structure: `response.choices[0].message.content`

4. **Output Format**
   - Single JSON line to stdout: `{"answer": "...", "tool_calls": []}`
   - All debug/logging output to stderr using `print(..., file=sys.stderr)`
   - Exit code 0 on success

### Error Handling

- Missing command-line argument → print usage to stderr, exit 1
- Missing/invalid `.env.agent.secret` → print error to stderr, exit 1
- HTTP request failure → print error to stderr, exit 1
- Invalid LLM response → print error to stderr, exit 1
- Timeout > 60 seconds → let it fail naturally

### Testing Strategy

Create one regression test that:

1. Runs `agent.py` as a subprocess with a test question
2. Parses stdout as JSON
3. Verifies `answer` field exists and is non-empty
4. Verifies `tool_calls` field exists and is an empty array

### Files to Create

1. `plans/task-1.md` - This plan
2. `.env.agent.secret` - Environment configuration (copy from `.env.agent.example`)
3. `agent.py` - Main CLI agent
4. `AGENT.md` - Documentation (update existing file)
5. `backend/tests/e2e/test_agent_task1.py` - Regression test
