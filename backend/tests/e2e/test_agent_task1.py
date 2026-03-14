"""Regression tests for agent.py (Task 1)."""

import json
import subprocess
import sys
from pathlib import Path


def test_agent_returns_valid_json() -> None:
    """Test that agent.py outputs valid JSON with required fields."""
    agent_path = Path(__file__).parent.parent.parent.parent / "agent.py"

    result = subprocess.run(
        [sys.executable, "-m", "uv", "run", str(agent_path), "What is 2+2?"],
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

    # Verify tool_calls is empty for Task 1
    assert len(output["tool_calls"]) == 0, "'tool_calls' must be empty for Task 1"
