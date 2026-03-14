"""Regression tests for agent.py (Task 2 - Documentation Agent)."""

import json
import subprocess
import sys
from pathlib import Path


def test_merge_conflict_question_uses_read_file() -> None:
    """Test that asking about merge conflicts uses read_file and references git-workflow.md."""
    agent_path = Path(__file__).parent.parent / "agent.py"

    result = subprocess.run(
        ["uv", "run", str(agent_path), "How do you resolve a merge conflict?"],
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

    # Verify read_file was used
    tools_used = [call["tool"] for call in output["tool_calls"]]
    assert "read_file" in tools_used, "Expected 'read_file' to be called"

    # Verify source references git-workflow.md
    assert "git-workflow.md" in output["source"], (
        f"Expected 'git-workflow.md' in source, got: {output['source']}"
    )


def test_wiki_listing_question_uses_list_files() -> None:
    """Test that asking about wiki files uses list_files tool."""
    agent_path = Path(__file__).parent.parent / "agent.py"

    result = subprocess.run(
        ["uv", "run", str(agent_path), "What files are in the wiki?"],
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

    # Verify list_files was used
    tools_used = [call["tool"] for call in output["tool_calls"]]
    assert "list_files" in tools_used, "Expected 'list_files' to be called"
