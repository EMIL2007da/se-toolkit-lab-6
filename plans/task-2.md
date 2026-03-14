# Task 2: The Documentation Agent - Implementation Plan

## Overview

This task extends the Task 1 agent with **tools** (`read_file`, `list_files`) and an **agentic loop** that allows the LLM to discover and read wiki files to answer questions.

## Tool Schemas

### `read_file`

**Purpose:** Read a file from the project repository.

**Schema:**
```json
{
  "name": "read_file",
  "description": "Read a file from the project repository",
  "parameters": {
    "type": "object",
    "properties": {
      "path": {
        "type": "string",
        "description": "Relative path from project root (e.g., 'wiki/git-workflow.md')"
      }
    },
    "required": ["path"]
  }
}
```

**Implementation:**
- Accept `path` parameter
- Validate path doesn't contain `../` (path traversal attack)
- Resolve path relative to project root
- Check file exists and is within project directory
- Return file contents as string, or error message

### `list_files`

**Purpose:** List files and directories at a given path.

**Schema:**
```json
{
  "name": "list_files",
  "description": "List files and directories in a directory",
  "parameters": {
    "type": "object",
    "properties": {
      "path": {
        "type": "string",
        "description": "Relative directory path from project root (e.g., 'wiki')"
      }
    },
    "required": ["path"]
  }
}
```

**Implementation:**
- Accept `path` parameter
- Validate path doesn't contain `../` (path traversal attack)
- Resolve path relative to project root
- Check directory exists and is within project directory
- Return newline-separated listing of entries

## Path Security

Both tools must prevent accessing files outside the project directory:

1. **Reject `../` patterns:** Check if the path contains `..` anywhere
2. **Resolve to absolute path:** Use `Path.resolve()` to get the canonical path
3. **Verify within project root:** Ensure the resolved path starts with the project root path
4. **Error on violation:** Return a clear error message if path is invalid

```python
def is_safe_path(path: str, project_root: Path) -> tuple[bool, Path]:
    """Validate and resolve a relative path safely."""
    # Reject path traversal attempts
    if ".." in path:
        return False, Path("")
    
    # Resolve to absolute path
    full_path = (project_root / path).resolve()
    
    # Verify it's within project root
    if not str(full_path).startswith(str(project_root)):
        return False, Path("")
    
    return True, full_path
```

## Agentic Loop

The agentic loop enables multi-step reasoning:

```
1. Send user question + tool definitions to LLM
2. Parse LLM response
3. If response contains tool_calls:
   a. Execute each tool
   b. Append results as 'tool' role messages
   c. Send back to LLM
   d. Repeat (max 10 iterations)
4. If response is text (no tool_calls):
   a. Extract answer and source
   b. Output JSON and exit
```

**Implementation:**
- Maintain a conversation history (list of messages)
- Track tool call count (max 10)
- After each tool execution, append result to messages and call LLM again
- Stop when LLM returns text answer or max calls reached

## System Prompt Strategy

The system prompt should guide the LLM to:

1. **Use tools effectively:**
   - First use `list_files` to discover relevant wiki files
   - Then use `read_file` to read specific files
   - Extract the answer from file contents

2. **Include source references:**
   - Always identify which file and section contains the answer
   - Format: `wiki/filename.md#section-anchor`

3. **Return structured output:**
   - Answer should be concise and accurate
   - Source must be a valid file path with section anchor

**Example system prompt:**
```
You are a documentation assistant that answers questions by reading wiki files.

Available tools:
- list_files(path): List files in a directory
- read_file(path): Read contents of a file

Process:
1. Use list_files to discover relevant wiki files
2. Use read_file to read specific files
3. Find the answer in the file contents
4. Return the answer with a source reference (file#section)

Always include the source field with format: wiki/filename.md#section-anchor
```

## Output Format

```json
{
  "answer": "The LLM's answer to the question",
  "source": "wiki/git-workflow.md#resolving-merge-conflicts",
  "tool_calls": [
    {
      "tool": "list_files",
      "args": {"path": "wiki"},
      "result": "git-workflow.md\n..."
    },
    {
      "tool": "read_file",
      "args": {"path": "wiki/git-workflow.md"},
      "result": "..."
    }
  ]
}
```

## Files to Modify

1. **`agent.py`** - Add tools, agentic loop, system prompt
2. **`AGENT.md`** - Document the new architecture
3. **`tests/test_agent_task2.py`** - Add 2 regression tests

## Testing Strategy

Two regression tests:

1. **Test merge conflict question:**
   - Question: "How do you resolve a merge conflict?"
   - Expected: `read_file` in tool_calls, `wiki/git-workflow.md` in source

2. **Test wiki listing question:**
   - Question: "What files are in the wiki?"
   - Expected: `list_files` in tool_calls

Tests will:
- Run `agent.py` as subprocess
- Parse JSON output
- Verify required fields exist
- Verify correct tools were called
- Verify source field contains expected file

## Error Handling

- **Tool execution errors:** Return error message as tool result, let LLM decide next step
- **Max tool calls reached:** Use whatever answer is available, note in output
- **Invalid tool arguments:** Return error message to LLM
- **LLM API errors:** Exit with error message to stderr
