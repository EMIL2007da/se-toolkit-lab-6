"""Regression tests for agent.py (Task 3 - System Agent)."""

import json
import subprocess
import sys
from pathlib import Path


def test_framework_question_uses_read_file() -> None:
    """Test that asking about the backend framework uses read_file on source code."""
    agent_path = Path(__file__).parent.parent / "agent.py"

    result = subprocess.run(
        ["uv", "run", str(agent_path), "What Python web framework does the backend use?"],
        capture_output=True,
        text=True,
        timeout=60,
    )

    # Check exit code
    assert result.returncode == 0, f"Agent failed: {result.stderr}"

    # Parse stdout as JSON
    output = json.loads(result.stdout)

    # Verify required fields exist
    assert "answer" in output, "Missing 'answer' field in output"
    assert "source" in output, "Missing 'source' field in output"
    assert "tool_calls" in output, "Missing 'tool_calls' field in output"

    # Verify field types
    assert isinstance(output["answer"], str), "'answer' must be a string"
    assert isinstance(output["source"], str), "'source' must be a string"
    assert isinstance(output["tool_calls"], list), "'tool_calls' must be an array"

    # Verify answer is non-empty
    assert len(output["answer"]) > 0, "'answer' must not be empty"

    # Verify tool_calls is populated (at least one tool was called)
    assert len(output["tool_calls"]) > 0, "'tool_calls' must not be empty"

    # Verify read_file was used (should read backend/app/main.py or similar)
    tools_used = [call["tool"] for call in output["tool_calls"]]
    assert "read_file" in tools_used, "Expected 'read_file' to be called"

    # Verify answer mentions FastAPI
    assert "fastapi" in output["answer"].lower(), (
        f"Expected 'FastAPI' in answer, got: {output['answer']}"
    )


def test_database_query_uses_query_api() -> None:
    """Test that asking about database items uses query_api tool."""
    agent_path = Path(__file__).parent.parent / "agent.py"

    result = subprocess.run(
        ["uv", "run", str(agent_path), "How many items are currently stored in the database?"],
        capture_output=True,
        text=True,
        timeout=60,
    )

    # Check exit code
    assert result.returncode == 0, f"Agent failed: {result.stderr}"

    # Parse stdout as JSON
    output = json.loads(result.stdout)

    # Verify required fields exist
    assert "answer" in output, "Missing 'answer' field in output"
    assert "tool_calls" in output, "Missing 'tool_calls' field in output"

    # Verify field types
    assert isinstance(output["answer"], str), "'answer' must be a string"
    assert isinstance(output["tool_calls"], list), "'tool_calls' must be an array"

    # Verify answer is non-empty
    assert len(output["answer"]) > 0, "'answer' must not be empty"

    # Verify tool_calls is populated (at least one tool was called)
    assert len(output["tool_calls"]) > 0, "'tool_calls' must not be empty"

    # Verify query_api was used
    tools_used = [call["tool"] for call in output["tool_calls"]]
    assert "query_api" in tools_used, "Expected 'query_api' to be called"

    # Verify answer contains a number (the item count)
    import re
    numbers = re.findall(r"\d+", output["answer"])
    assert len(numbers) > 0, (
        f"Expected a number in answer (item count), got: {output['answer']}"
    )
