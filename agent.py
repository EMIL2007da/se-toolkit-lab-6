#!/usr/bin/env python3
"""
Agent CLI - Calls an LLM and returns a structured JSON answer.

Usage:
    uv run agent.py "Your question here"

Output:
    JSON with 'answer' and 'tool_calls' fields to stdout.
    All debug output goes to stderr.
"""

import json
import os
import sys
from pathlib import Path

import httpx


def load_env() -> dict[str, str]:
    """Load environment variables from .env.agent.secret."""
    env_file = Path(__file__).parent / ".env.agent.secret"
    env_vars = {}

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


async def call_llm(question: str, env: dict[str, str]) -> str:
    """Call the LLM API and return the answer."""
    api_base = env["LLM_API_BASE"]
    api_key = env["LLM_API_KEY"]
    model = env["LLM_MODEL"]

    print(f"Calling LLM: {model}", file=sys.stderr)
    print(f"API Base: {api_base}", file=sys.stderr)

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": question}],
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{api_base}/chat/completions",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        data = response.json()

    # Extract answer from response
    try:
        answer = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        print(f"Error: Unexpected LLM response format: {e}", file=sys.stderr)
        print(f"Response: {data}", file=sys.stderr)
        sys.exit(1)

    return answer


def main() -> None:
    """Main entry point."""
    # Parse command-line arguments
    if len(sys.argv) < 2:
        print("Usage: uv run agent.py \"<question>\"", file=sys.stderr)
        sys.exit(1)

    question = sys.argv[1]
    print(f"Question: {question}", file=sys.stderr)

    # Load and validate environment
    env = load_env()
    validate_env(env)

    # Call LLM and get answer
    import asyncio

    answer = asyncio.run(call_llm(question, env))
    print(f"Answer received", file=sys.stderr)

    # Output JSON result
    result = {
        "answer": answer,
        "tool_calls": [],
    }
    print(json.dumps(result))


if __name__ == "__main__":
    main()
