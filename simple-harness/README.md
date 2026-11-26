# simple-harness

The smallest useful agent harness: **~150 lines, Python stdlib only, one file.**

## What is a harness?

A model API is just a function: `messages -> message`. By itself it can't touch
your files, run commands, or remember anything between calls. A **harness** is
the loop you wrap around that function to give the model hands:

```
            ┌──────────────────────────────────────────┐
   prompt ─▶│  messages ──▶ model API ──▶ tool_calls?   │
            │       ▲                    │            │
            │       │              yes   ▼            │
            │       │         run tool, append result │
            │       │                    │            │
            │       └──── no tool calls ──┘            │
            │            → print answer, stop         │
            └──────────────────────────────────────────┘
```

That loop — *call model → if it asks for tools, run them and feed results back →
repeat until it answers* — is the entire idea behind every agent framework
(LangGraph, CrewAI, the agent0 repo one directory up, Claude Code itself).
Everything else in a real harness is this loop plus safety, memory, verification
and observability.

## Run it

```bash
# free key: https://console.groq.com/keys
set GROQ_API_KEY=gsk_...
python harness.py "create hello.py that prints hi, then run it"
```

Any OpenAI-compatible endpoint works — point `API`/`MODEL` at Gemini, OpenAI,
Ollama (`http://localhost:11434/v1`), etc.

## What to notice when you run it

- The model never "does" anything. It emits JSON saying *which tool to call and
  with what arguments*. `run_tool` executes it; the result goes back as a
  `role: "tool"` message. Next call, the model sees its own history and decides
  again.
- `MAX_STEPS` is the stop condition. Without it a confused model loops forever —
  every real harness needs one (agent0 calls it `max_steps` too).
- `safe()` is the only security: paths can't escape `./workspace`. Real harnesses
  add sandboxes, approval gates and policy on top of exactly this.
- Tool errors are returned to the model as text, not raised — the model reads
  "error: ..." and tries again. That's the whole recovery mechanism.

## Map to agent0

| simple-harness | agent0 |
|---|---|
| `chat()` | `models/chat.py` + provider profiles |
| `TOOLS` / `TOOL_SCHEMAS` | `tools/builtin.py` + policy permissions |
| the `for step` loop | `orchestrator/steps.py` |
| `MAX_STEPS` | `Budget.max_steps` |
| `safe()` | `sandbox/` + `policy/` |
| printed answer | verify checks → verdicts → receipts |
