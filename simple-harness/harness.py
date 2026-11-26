#!/usr/bin/env python3
"""simple-harness: the smallest useful agent harness (~150 lines, stdlib only).

What is a "harness"? The model is just a text-in/text-out function. A harness is
the loop around it that gives the model *hands*: tools it can call, results it can
read back, and a stop condition. This file is that loop and nothing else —
no framework, no database, no dashboard. Read it top to bottom; it IS the lesson.

Run:   set GROQ_API_KEY=...   (free key: https://console.groq.com)
       python harness.py "create hello.py that prints hi and run it"
"""

import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

API = "https://api.groq.com/openai/v1/chat/completions"
MODEL = os.environ.get("HARNESS_MODEL", "openai/gpt-oss-20b")
MAX_STEPS = 15
WORKSPACE = Path(os.environ.get("HARNESS_WORKSPACE", "./workspace")).resolve()
WORKSPACE.mkdir(exist_ok=True)

SYSTEM = """You are a helpful agent with tools. Work step by step.
Rules: use tools to inspect/act, never claim you did something you didn't.
All file paths are relative to the workspace. When the task is done, reply with a
short summary and no tool calls."""


# --- tools: the only things the model can do to the world -------------------
# Each returns a string. The model sees that string as the tool result.

def safe(path: str) -> Path:
    p = (WORKSPACE / path).resolve()
    if not p.is_relative_to(WORKSPACE):
        raise ValueError(f"path escapes workspace: {path}")
    return p


def tool_shell(command: str) -> str:
    r = subprocess.run(command, shell=True, cwd=WORKSPACE, capture_output=True,
                       text=True, timeout=60)
    return f"exit {r.returncode}\n{(r.stdout + r.stderr)[-4000:]}"


def tool_read_file(path: str) -> str:
    return safe(path).read_text()[:8000]


def tool_write_file(path: str, content: str) -> str:
    p = safe(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return f"wrote {len(content)} chars to {path}"


def tool_list_files(path: str = ".") -> str:
    return "\n".join(str(p.relative_to(WORKSPACE)) for p in sorted(safe(path).rglob("*"))[:200])


TOOLS = {
    "shell": tool_shell,
    "read_file": tool_read_file,
    "write_file": tool_write_file,
    "list_files": tool_list_files,
}

def schema(name: str, description: str, props: dict, required: list[str]) -> dict:
    return {"type": "function", "function": {
        "name": name, "description": description,
        "parameters": {"type": "object", "properties": props, "required": required}}}


STR = {"type": "string"}
TOOL_SCHEMAS = [
    schema("shell", "Run a shell command in the workspace", {"command": STR}, ["command"]),
    schema("read_file", "Read a workspace file", {"path": STR}, ["path"]),
    schema("write_file", "Write a workspace file", {"path": STR, "content": STR}, ["path", "content"]),
    schema("list_files", "List workspace files", {"path": {**STR, "description": "optional subdir"}}, []),
]


def chat(messages: list[dict]) -> dict:
    """One call to the model. This is the ONLY place we talk to the API."""
    body = json.dumps({"model": MODEL, "messages": messages, "tools": TOOL_SCHEMAS}).encode()
    req = urllib.request.Request(API, data=body, headers={
        "Authorization": f"Bearer {os.environ['GROQ_API_KEY']}",
        "Content-Type": "application/json",
        # Cloudflare in front of Groq 403s the default Python-urllib user agent.
        "User-Agent": "simple-harness/1.0",
    })
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)["choices"][0]["message"]


def run_tool(name: str, args: dict) -> str:
    if name not in TOOLS:
        return f"error: unknown tool {name!r}"
    try:
        return TOOLS[name](**{k: str(v) for k, v in args.items()})
    except Exception as e:  # tool errors go back to the model, not crash the loop
        return f"error: {type(e).__name__}: {e}"


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit('usage: python harness.py "your task"')
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": sys.argv[1]},
    ]
    for step in range(1, MAX_STEPS + 1):
        msg = chat(messages)
        messages.append(msg)  # assistant turn (may contain tool_calls)
        calls = msg.get("tool_calls") or []
        if not calls:  # no tool calls = the model is done; its content is the answer
            print(f"\n[{MODEL} — {step} steps]\n{msg.get('content', '')}")
            return
        for call in calls:
            fn = call["function"]
            args = json.loads(fn.get("arguments") or "{}")
            print(f"  step {step}: {fn['name']}({json.dumps(args)[:100]})")
            result = run_tool(fn["name"], args)
            messages.append({"role": "tool", "tool_call_id": call["id"],
                             "content": result})
    print("\n[max steps reached — harness stopped the loop]")


if __name__ == "__main__":
    main()
