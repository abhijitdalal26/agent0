# Context engineering for long-running agents

Agents fail on long tasks mostly through context rot: the longer the
conversation, the more irrelevant tokens dilute the instructions that matter.

Techniques that work:

- **Workspace as memory** — write intermediate results to files and re-read
  them, instead of carrying everything in the prompt.
- **Skills on demand** — keep specialist instructions out of the system prompt
  and load them only when relevant (`load_skill`).
- **Memory recall** — inject only the few facts and past runs relevant to the
  current task, not the whole history.
- **Fresh attempts** — when a run retries, start clean with the failure
  feedback attached rather than continuing a polluted context.

The executor's prompt should contain the task, the plan, the acceptance
criteria, and pointers — not the entire transcript of every previous attempt.
