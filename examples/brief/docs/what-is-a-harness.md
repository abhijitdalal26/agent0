# What an agent harness is

An agent harness is the software layer that wraps a language model and turns it
into a system that can act: it supplies tools, manages context, enforces
budgets, records an audit trail, and verifies outputs before they count.

The model alone is a text predictor. The harness is what makes it an agent:

- **Tools** give the model hands — shell, files, web, databases, media.
- **Context management** decides what the model sees each turn; long tasks
  die without it.
- **Budgets** cap steps, time and spend so a loop cannot run away.
- **Verification** checks the result independently of the model's own claims.
- **Audit trail** records what happened, in order, tamper-evidently.

A useful rule of thumb: if removing the model leaves nothing, you built a
chatbot. If removing the model leaves an empty shell that still tracks state,
you built a harness.

## Harness vs framework

Frameworks (LangGraph, CrewAI, the OpenAI Agents SDK) provide building blocks
you assemble. A harness is an opinionated runtime: it already decides the loop
shape, the permission model, and the definition of done. Most production
systems end up being both — a framework inside a harness.
