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
    env_file = PROJECT_ROOT / ".env.agent.secret"
    env_vars: dict[str, str] = {}

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
    ]


def execute_tool(tool_name: str, args: dict[str, Any]) -> str:
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
        return read_file(path)
    elif tool_name == "list_files":
        path = args.get("path", "")
        return list_files(path)
    else:
        return f"Error: Unknown tool '{tool_name}'"


def get_system_prompt() -> str:
    """Return the system prompt for the documentation agent."""
    return """You are a documentation assistant that answers questions by reading wiki files from a software engineering project.

Available tools:
- list_files(path): List files and directories in a directory. Use this first to discover what wiki files are available.
- read_file(path): Read the contents of a specific file. Use this to read wiki files and find answers.

Process:
1. Use list_files to discover relevant wiki files (start with 'wiki' directory)
2. Use read_file to read specific files that might contain the answer
3. Find the answer in the file contents
4. Return the answer with a source reference

Important:
- Always include the source field with format: wiki/filename.md#section-anchor
- Section anchors are lowercase with hyphens instead of spaces (e.g., 'resolving-merge-conflicts')
- If you can't find an exact section, use just the file path
- Be concise and accurate in your answers
- Only use the tools available to you (read_file, list_files)"""


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
            result = execute_tool(tool_name, tool_args)

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
