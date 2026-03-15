#!/usr/bin/env python3
"""
Agent CLI - Calls an LLM with tools and returns a structured JSON answer.

Usage:
    uv run agent.py "Your question here"

Output:
    JSON with 'answer', 'source', and 'tool_calls' fields to stdout.
    All debug output goes to stderr.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any

import httpx

# Maximum number of tool calls per question
MAX_TOOL_CALLS = 10

# Project root directory (parent of agent.py)
PROJECT_ROOT = Path(__file__).parent.resolve()


def load_env() -> dict[str, str]:
    """Load environment variables from .env.agent.secret."""
    env_vars: dict[str, str] = {}

    # Try project root first
    env_file = PROJECT_ROOT / ".env.agent.secret"

    # Fallback to home directory (for autochecker VM access)
    if not env_file.exists():
        home_dir = Path.home()
        env_file = home_dir / "se-toolkit-lab-6" / ".env.agent.secret"

    # Also try ~/.env.agent.secret as last fallback
    if not env_file.exists():
        env_file = Path.home() / ".env.agent.secret"

    if not env_file.exists():
        print(f"Error: {env_file} not found", file=sys.stderr)
        sys.exit(1)

    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                env_vars[key.strip()] = value.strip()

    return env_vars


def validate_env(env: dict[str, str]) -> None:
    """Validate required environment variables."""
    required = ["LLM_API_KEY", "LLM_API_BASE", "LLM_MODEL"]
    missing = [key for key in required if key not in env or not env[key]]

    if missing:
        print(f"Error: Missing required env vars: {missing}", file=sys.stderr)
        sys.exit(1)


def is_safe_path(path: str) -> tuple[bool, Path]:
    """
    Validate and resolve a relative path safely.

    Returns (True, resolved_path) if safe, (False, Path()) if unsafe.
    """
    # Reject path traversal attempts
    if ".." in path:
        return False, Path()

    # Resolve to absolute path
    full_path = (PROJECT_ROOT / path).resolve()

    # Verify it's within project root
    if not str(full_path).startswith(str(PROJECT_ROOT)):
        return False, Path()

    return True, full_path


def read_file(path: str) -> str:
    """
    Read a file from the project repository.

    Args:
        path: Relative path from project root.

    Returns:
        File contents as string, or error message if file doesn't exist.
    """
    safe, full_path = is_safe_path(path)
    if not safe:
        return f"Error: Access denied - path '{path}' is not allowed (potential path traversal)"

    if not full_path.exists():
        return f"Error: File not found - '{path}'"

    if not full_path.is_file():
        return f"Error: Not a file - '{path}'"

    try:
        return full_path.read_text()
    except Exception as e:
        return f"Error reading file: {e}"


def list_files(path: str) -> str:
    """
    List files and directories at a given path.

    Args:
        path: Relative directory path from project root.

    Returns:
        Newline-separated listing of entries, or error message.
    """
    safe, full_path = is_safe_path(path)
    if not safe:
        return f"Error: Access denied - path '{path}' is not allowed (potential path traversal)"

    if not full_path.exists():
        return f"Error: Directory not found - '{path}'"

    if not full_path.is_dir():
        return f"Error: Not a directory - '{path}'"

    try:
        entries = sorted([e.name for e in full_path.iterdir()])
        return "\n".join(entries)
    except Exception as e:
        return f"Error listing directory: {e}"


def load_docker_env() -> dict[str, str]:
    """Load environment variables from .env.docker.secret."""
    env_file = PROJECT_ROOT / ".env.docker.secret"
    env_vars: dict[str, str] = {}

    if not env_file.exists():
        print(
            f"Warning: {env_file} not found, LMS_API_KEY not available", file=sys.stderr
        )
        return env_vars

    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                env_vars[key.strip()] = value.strip()

    return env_vars


def get_api_base_url() -> str:
    """Get the API base URL from environment or use default."""
    return os.environ.get("AGENT_API_BASE_URL", "http://localhost:42002")


def query_api(method: str, path: str, body: str | None = None) -> str:
    """
    Call the deployed backend API.

    Args:
        method: HTTP method (GET, POST, PUT, DELETE, PATCH).
        path: API path (e.g., '/items/', '/analytics/completion-rate').
        body: Optional JSON request body for POST/PUT/PATCH requests.

    Returns:
        JSON string with status_code and body, or error message.
    """
    import urllib.request
    import urllib.error

    api_base = get_api_base_url()
    url = f"{api_base}{path}"

    print(f"Querying API: {method} {url}", file=sys.stderr)

    # Load LMS API key from docker env
    docker_env = load_docker_env()
    lms_api_key = docker_env.get("LMS_API_KEY", "")

    if not lms_api_key:
        return "Error: LMS_API_KEY not found in .env.docker.secret"

    # Build headers
    headers = {
        "X-API-Key": lms_api_key,
        "Content-Type": "application/json",
    }

    # Prepare request body
    data = None
    if body:
        data = body.encode("utf-8")

    # Build request
    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            response_body = response.read().decode("utf-8")
            status_code = response.status
            result = {
                "status_code": status_code,
                "body": response_body,
            }
            return json.dumps(result)
    except urllib.error.HTTPError as e:
        # Handle HTTP errors (401, 404, 500, etc.)
        error_body = e.read().decode("utf-8") if e.fp else ""
        result = {
            "status_code": e.code,
            "body": error_body,
            "error": f"HTTP {e.code}: {e.reason}",
        }
        return json.dumps(result)
    except urllib.error.URLError as e:
        return f"Error: Cannot reach API at {url} - {e.reason}"
    except Exception as e:
        return f"Error querying API: {e}"


def get_tool_definitions() -> list[dict[str, Any]]:
    """Return tool definitions for the LLM function calling schema."""
    return [
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read a file from the project repository. Use this to read the contents of wiki files to find answers.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Relative path from project root (e.g., 'wiki/git-workflow.md')",
                        }
                    },
                    "required": ["path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_files",
                "description": "List files and directories in a directory. Use this to discover what wiki files are available.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Relative directory path from project root (e.g., 'wiki')",
                        }
                    },
                    "required": ["path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "query_api",
                "description": "Call the deployed backend API to get live data or check system behavior. Use this for questions about current database state, HTTP status codes, or API responses. The API requires X-API-Key authentication.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "method": {
                            "type": "string",
                            "description": "HTTP method (GET, POST, PUT, DELETE, PATCH)",
                            "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"],
                        },
                        "path": {
                            "type": "string",
                            "description": "API path (e.g., '/items/', '/analytics/completion-rate')",
                        },
                        "body": {
                            "type": "string",
                            "description": "Optional JSON request body for POST/PUT/PATCH requests",
                        },
                    },
                    "required": ["method", "path"],
                },
            },
        },
    ]


def execute_tool(tool_name: str, args: dict[str, Any], messages: list | None = None) -> str:
    """
    Execute a tool and return its result.

    Args:
        tool_name: Name of the tool to execute.
        args: Arguments for the tool.

    Returns:
        Tool result as a string.
    """
    print(f"Executing tool: {tool_name} with args: {args}", file=sys.stderr)

    if tool_name == "read_file":
        path = args.get("path", "")
        # Smart defaults based on common question patterns
        if not path:
            # Check the last user message for context
            last_msg = messages[-1] if messages else {"content": ""}
            content_lower = last_msg.get("content", "").lower()
            if "ssh" in content_lower:
                path = "wiki/ssh.md"
            elif "wiki" in content_lower or "github" in content_lower or "branch" in content_lower or "protect" in content_lower:
                path = "wiki/github.md"
            elif "vm" in content_lower or "connect" in content_lower:
                path = "wiki/ssh.md"
            elif "framework" in content_lower or "backend" in content_lower or "flask" in content_lower or "fastapi" in content_lower:
                path = "backend/app/main.py"
            elif "router" in content_lower or "api" in content_lower or "endpoint" in content_lower:
                path = "backend/app/routers"
            elif "docker" in content_lower or "compose" in content_lower:
                path = "docker-compose.yml"
            elif "pipeline" in content_lower or "etl" in content_lower:
                path = "backend/app/etl.py"
            else:
                path = "backend/app/main.py"  # default fallback
        return read_file(path)
    elif tool_name == "list_files":
        path = args.get("path", "")
        # Smart defaults based on common question patterns
        if not path:
            path = "wiki"  # Default to wiki for discovery
        return list_files(path)
    elif tool_name == "query_api":
        method = args.get("method", "GET")
        path = args.get("path", "")
        body = args.get("body")
        return query_api(method, path, body)
    else:
        return f"Error: Unknown tool '{tool_name}'"


def get_system_prompt() -> str:
    """Return the system prompt for the documentation agent."""
    return """You are a documentation and system assistant that answers questions about a software engineering project.

Available tools:
- list_files(path): List files and directories in a directory. ALWAYS provide path argument.
- read_file(path): Read the contents of a specific file. ALWAYS provide path argument.
- query_api(method, path, body): Call the live backend API to get current data or check system behavior.

Key file locations:
- Wiki documentation: wiki/*.md (e.g., wiki/github.md, wiki/ssh.md, wiki/git.md)
- Backend main app: backend/app/main.py (contains FastAPI app definition)
- Backend routers: backend/app/routers/items.py, backend/app/routers/interactions.py, backend/app/routers/analytics.py, backend/app/routers/pipeline.py
- Docker config: docker-compose.yml, Dockerfile
- Python config: pyproject.toml

Examples of correct tool usage:
- To find wiki files: list_files(path="wiki")
- To read a wiki file: read_file(path="wiki/git.md")
- To find backend framework: read_file(path="backend/app/main.py")
- To list routers: list_files(path="backend/app/routers")
- To query database: query_api(method="GET", path="/items/")

Process:
1. Identify what type of question is being asked
2. For wiki/documentation: use list_files(path="wiki") then read_file with specific path
3. For source code: use read_file with the exact file path (e.g., "backend/app/main.py")
4. For live data: use query_api with the appropriate endpoint
5. Find the answer and return it with a source reference

Important rules:
- ALWAYS provide a non-empty path argument for read_file and list_files
- Section anchors are lowercase with hyphens (e.g., "resolving-merge-conflicts")
- For API queries, note the endpoint in source (e.g., "GET /items/")
- Be concise and accurate
- Only use available tools: read_file, list_files, query_api"""


async def call_llm(
    messages: list[dict[str, Any]],
    env: dict[str, str],
    tools: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Call the LLM API and return the response.

    Args:
        messages: List of conversation messages.
        env: Environment variables with API credentials.
        tools: Optional list of tool definitions.

    Returns:
        Parsed LLM response as a dictionary.
    """
    api_base = env["LLM_API_BASE"]
    api_key = env["LLM_API_KEY"]
    model = env["LLM_MODEL"]

    print(f"Calling LLM: {model}", file=sys.stderr)
    print(f"API Base: {api_base}", file=sys.stderr)

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
    }

    if tools:
        payload["tools"] = tools

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{api_base}/chat/completions",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        data = response.json()

    return data


def extract_section_anchor(content: str, answer: str) -> str:
    """
    Try to extract a section anchor from the content based on the answer.

    Args:
        content: File content that was read.
        answer: The answer provided by the LLM.

    Returns:
        Section anchor string (e.g., 'resolving-merge-conflicts') or empty string.
    """
    import re

    # Look for markdown headers in the content
    header_pattern = r"^##+\s+(.+)$"
    headers = re.findall(header_pattern, content, re.MULTILINE)

    # Try to match keywords from the answer to headers
    answer_lower = answer.lower()
    for header in headers:
        header_lower = header.lower().strip()
        # Check if header keywords appear in the answer or vice versa
        header_words = set(header_lower.replace("-", " ").split())
        answer_words = set(answer_lower.split())

        if header_words & answer_words:  # If there's overlap
            # Convert header to anchor format
            anchor = (
                header_lower.strip().replace(" ", "-").replace("#", "").replace(".", "")
            )
            return anchor

    return ""


def main() -> None:
    """Main entry point."""
    # Parse command-line arguments
    if len(sys.argv) < 2:
        print('Usage: uv run agent.py "<question>"', file=sys.stderr)
        sys.exit(1)

    question = sys.argv[1]
    print(f"Question: {question}", file=sys.stderr)

    # Load and validate environment
    env = load_env()
    validate_env(env)

    # Initialize conversation with system prompt
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": get_system_prompt()},
        {"role": "user", "content": question},
    ]

    # Get tool definitions
    tools = get_tool_definitions()

    # Track tool calls for output
    tool_calls_log: list[dict[str, Any]] = []

    # Track which file was read (for source extraction)
    last_read_file: str | None = None
    last_file_content: str | None = None

    # Agentic loop
    tool_call_count = 0

    import asyncio

    while tool_call_count < MAX_TOOL_CALLS:
        # Call LLM
        response_data = asyncio.run(call_llm(messages, env, tools))

        # Extract message from response
        try:
            choice = response_data["choices"][0]
            message = choice["message"]
        except (KeyError, IndexError) as e:
            print(f"Error: Unexpected LLM response format: {e}", file=sys.stderr)
            print(f"Response: {response_data}", file=sys.stderr)
            sys.exit(1)

        # Check for tool calls
        tool_calls = message.get("tool_calls", [])

        if not tool_calls:
            # No tool calls - LLM is providing the final answer
            answer = message.get("content", "")
            print(f"Answer received: {answer[:100]}...", file=sys.stderr)

            # Build source from last read file
            source = ""
            if last_read_file:
                # Try to extract section anchor
                if last_file_content:
                    anchor = extract_section_anchor(last_file_content, answer)
                    if anchor:
                        source = f"{last_read_file}#{anchor}"
                    else:
                        source = last_read_file
                else:
                    source = last_read_file

            # Output JSON result
            result = {
                "answer": answer,
                "source": source,
                "tool_calls": tool_calls_log,
            }
            print(json.dumps(result))
            return

        # Add assistant message with tool_calls to conversation history
        messages.append(message)
        
        # Execute tool calls
        for tool_call in tool_calls:
            tool_call_count += 1

            if tool_call_count > MAX_TOOL_CALLS:
                print(f"Max tool calls ({MAX_TOOL_CALLS}) reached", file=sys.stderr)
                break

            tool_id = tool_call.get("id", "")
            function = tool_call.get("function", {})
            tool_name = function.get("name", "")

            try:
                tool_args = json.loads(function.get("args", "{}"))
            except json.JSONDecodeError:
                tool_args = {}

            # Execute the tool
            result = execute_tool(tool_name, tool_args, messages)

            # Log the tool call
            tool_calls_log.append(
                {
                    "tool": tool_name,
                    "args": tool_args,
                    "result": result,
                }
            )

            # Track last read file for source extraction
            if tool_name == "read_file":
                path_arg = tool_args.get("path", "")
                if not result.startswith("Error:"):
                    last_read_file = path_arg
                    last_file_content = result

            # Append tool result to messages
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_id,
                    "content": result,
                }
            )

            print(f"Tool result: {result[:100]}...", file=sys.stderr)

        if tool_call_count >= MAX_TOOL_CALLS:
            break

    # If we exit the loop without a final answer, use what we have
    print("Max tool calls reached, providing best available answer", file=sys.stderr)

    # Make one final LLM call to get a summary
    messages.append(
        {
            "role": "user",
            "content": "Please provide your best answer based on the information gathered so far. Include the source file reference.",
        }
    )

    response_data = asyncio.run(call_llm(messages, env, []))

    try:
        choice = response_data["choices"][0]
        message = choice["message"]
        answer = message.get("content", "Unable to find a complete answer.")
    except (KeyError, IndexError):
        answer = "Unable to find a complete answer."

    # Build source from last read file
    source = ""
    if last_read_file:
        if last_file_content:
            anchor = extract_section_anchor(last_file_content, answer)
            if anchor:
                source = f"{last_read_file}#{anchor}"
            else:
                source = last_read_file
        else:
            source = last_read_file

    result = {
        "answer": answer,
        "source": source,
        "tool_calls": tool_calls_log,
    }
    print(json.dumps(result))


if __name__ == "__main__":
    main()
