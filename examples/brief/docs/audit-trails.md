# Audit trails and receipts

A tamper-evident audit trail records every event of a run — plan created,
tool calls, model calls, check verdicts, approvals — as a hash chain: each
event stores the hash of the previous one, so editing or deleting any past
event breaks verification of everything after it.

Verification walks the chain and recomputes hashes; a signed receipt bundles
the events plus an HMAC signature so a third party can confirm the trail was
not altered after the fact.

## Why it matters

- **Debugging**: "what did the agent actually do" is a query, not a guess.
- **Compliance**: regulated work needs provable records of automated actions.
- **Trust**: a demo that shows `verify: ok` on stage is a different claim than
  "trust me, it worked".

## Practical notes

- Hash the canonical serialization of each event plus `prev_hash`.
- Keep verification cheap enough to run on every run page load.
- Legacy rows written before chaining existed must be backfilled or they
  fail verification honestly — that is the point of the design.
