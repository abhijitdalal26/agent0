# Verification patterns for agent output

The core failure mode of agents is confident wrongness: the model says "done"
and the artifact is broken. Verification patterns, cheapest first:

1. **Deterministic checks** — files exist, schemas parse, regexes match,
   commands exit 0, images have the right dimensions. Free, instant, and they
   never hallucinate.
2. **Groundedness checks** — every factual claim must carry a `[src:<id>]`
   citation that resolves to retrieved data. Claims without citations, or
   citations to sources that do not state the claim, fail.
3. **LLM-judge checks** — a second model scores subjective quality against a
   rubric (tone, clarity, completeness). Use only where deterministic checks
   cannot decide; judges cost money and can be wrong.
4. **Human checks** — a person approves before anything outward-facing
   happens: sending, publishing, paying, deleting.

Ordering matters: run cheap checks first and skip expensive ones when an
upstream gate already failed.

## Anti-patterns

- Trusting the executor's self-assessment ("I wrote the file") as evidence.
- Letting the planner invent acceptance criteria that contradict the user's.
- Running an LLM judge where a regex would do.
