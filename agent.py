import sys
import json
import os
import requests
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv(".env.agent.secret")
load_dotenv(".env.docker.secret")

PROJECT_ROOT = os.path.realpath(os.path.dirname(__file__))
AGENT_API_BASE_URL = os.environ.get("AGENT_API_BASE_URL", "http://localhost:42002")

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file from the project repository. Use for wiki docs, source code, Dockerfile, docker-compose.yml, ETL pipeline code, backend routers.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path from project root.",
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
            "description": "List files and directories at a given path in the project repository. Use to discover router modules, backend files, wiki files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative directory path from project root.",
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
            "description": "Call the deployed backend API. Use for live data: item counts, HTTP status codes, analytics endpoints, endpoint errors. Set auth=false to test unauthenticated requests.",
            "parameters": {
                "type": "object",
                "properties": {
                    "method": {
                        "type": "string",
                        "description": "HTTP method: GET, POST, etc.",
                    },
                    "path": {
                        "type": "string",
                        "description": "API path with query params if needed, e.g. /items/ or /analytics/completion-rate?lab=lab-99",
                    },
                    "body": {
                        "type": "string",
                        "description": "Optional JSON request body.",
                    },
                    "auth": {
                        "type": "boolean",
                        "description": "Include auth header. Default true. Set false to test unauthenticated access.",
                    },
                },
                "required": ["method", "path"],
            },
        },
    },
]

SYSTEM_PROMPT = """You are a system and documentation assistant with three tools:

1. list_files — list files in a project directory
2. read_file — read project files (wiki, source code, configs, Dockerfile, docker-compose.yml, ETL code)
3. query_api — call the live backend API

Decision rules:
- Wiki or documentation questions → read_file on wiki/
- Source code, framework, architecture, ETL, request lifecycle → read_file on backend/ (use list_files first if needed)
- Live data, item counts, HTTP status codes → query_api
- Endpoint bug questions → query_api to reproduce the error, then read_file on the relevant source file to find the bug
- Router modules → list_files on backend/routers, then read_file if needed

Always include the source when available (file path + section anchor or endpoint path).
End your response with: SOURCE: <path#anchor> (or SOURCE: none)"""


def safe_path(relative_path):
    full = os.path.realpath(os.path.join(PROJECT_ROOT, relative_path))
    if not full.startswith(PROJECT_ROOT):
        raise ValueError(f"Access denied: {relative_path}")
    return full


def read_file(path):
    try:
        full = safe_path(path)
        with open(full, "r", encoding="utf-8") as f:
            return f.read()
    except ValueError as e:
        return str(e)
    except FileNotFoundError:
        return f"File not found: {path}"


def list_files(path):
    try:
        full = safe_path(path)
        entries = os.listdir(full)
        return "\n".join(sorted(entries))
    except ValueError as e:
        return str(e)
    except FileNotFoundError:
        return f"Directory not found: {path}"


def query_api(method, path, body=None, auth=True):
    url = AGENT_API_BASE_URL.rstrip("/") + path
    headers = {"Content-Type": "application/json"}
    if auth:
        headers["Authorization"] = f"Bearer {os.environ.get('LMS_API_KEY', '')}"
    try:
        resp = requests.request(
            method=method.upper(),
            url=url,
            headers=headers,
            data=body if body else None,
            timeout=15,
        )
        return json.dumps({"status_code": resp.status_code, "body": resp.text})
    except Exception as e:
        return json.dumps({"status_code": 0, "body": str(e)})


def execute_tool(name, args):
    if name == "read_file":
        return read_file(args["path"])
    elif name == "list_files":
        return list_files(args["path"])
    elif name == "query_api":
        return query_api(
            args["method"], args["path"], args.get("body"), args.get("auth", True)
        )
    return "Unknown tool"


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "No question provided"}))
        sys.exit(1)

    question = sys.argv[1]
    client = OpenAI(
        api_key=os.environ["LLM_API_KEY"],
        base_url=os.environ["LLM_API_BASE"],
    )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]

    all_tool_calls = []
    answer = ""
    source = ""

    for _ in range(10):
        print("Calling LLM...", file=sys.stderr)
        response = client.chat.completions.create(
            model=os.environ["LLM_MODEL"],
            messages=messages,
            tools=TOOLS,
            timeout=60,
        )

        msg = response.choices[0].message

        if msg.tool_calls:
            messages.append(
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in msg.tool_calls
                    ],
                }
            )
            for tc in msg.tool_calls:
                args = json.loads(tc.function.arguments)
                result = execute_tool(tc.function.name, args)
                print(f"Tool: {tc.function.name} {args}", file=sys.stderr)
                all_tool_calls.append(
                    {"tool": tc.function.name, "args": args, "result": result}
                )
                messages.append(
                    {"role": "tool", "tool_call_id": tc.id, "content": result}
                )
        else:
            answer_text = (msg.content or "").strip()
            if "SOURCE:" in answer_text:
                parts = answer_text.rsplit("SOURCE:", 1)
                answer = parts[0].strip()
                source = parts[1].strip()
                if source.lower() == "none":
                    source = ""
            else:
                answer = answer_text
                source = ""
            break

    output = {"answer": answer, "tool_calls": all_tool_calls}
    if source:
        output["source"] = source
    print(json.dumps(output))


if __name__ == "__main__":
    main()
