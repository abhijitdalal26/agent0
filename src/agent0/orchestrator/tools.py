from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic_ai import RunContext
from pydantic_ai.toolsets import FunctionToolset

from agent0.core.types import Capability, EventType, new_id
from agent0.knowledge.base import KnowledgeSource, SourceRecord
from agent0.models import media
from agent0.models.router import Router
from agent0.models.usage import UsageMeter
from agent0.tools.deps import ToolDeps


@dataclass
class RunDeps(ToolDeps):
    knowledge: dict[str, KnowledgeSource] = field(default_factory=dict)
    sources: list[SourceRecord] = field(default_factory=list)
    router: Router | None = None
    meter: UsageMeter | None = None
    artifacts: list[str] = field(default_factory=list)


def _render(records: list[SourceRecord]) -> str:
    if not records:
        return "No matching records. If the answer depends on this, say it is not in the data."
    return "\n\n".join(f"[src:{r.source_id}]\n{r.content}" for r in records)


async def _read(ctx: RunContext[RunDeps], source: str, records: list[SourceRecord], query: str) -> str:
    deps = ctx.deps
    known = {r.source_id for r in deps.sources}
    deps.sources.extend(r for r in records if r.source_id not in known)
    await deps.events.emit(
        deps.run_id,
        EventType.KNOWLEDGE_READ,
        {"source": source, "query": query[:300], "ids": [r.source_id for r in records]},
    )
    return _render(records)


def _source(deps: RunDeps, name: str) -> KnowledgeSource:
    if name not in deps.knowledge:
        raise ValueError(f"unknown source {name!r}; available: {', '.join(deps.knowledge) or 'none'}")
    return deps.knowledge[name]


async def list_sources(ctx: RunContext[RunDeps]) -> str:
    """List connected knowledge sources (databases, document sets) you can read facts from."""
    return "\n".join(f"{n} ({s.kind})" for n, s in ctx.deps.knowledge.items()) or "No sources connected."


async def search_knowledge(ctx: RunContext[RunDeps], source: str, query: str, limit: int = 5) -> str:
    """Search a document source. Cite every fact you use as [src:<id>] exactly as shown."""
    records = await _source(ctx.deps, source).search(query, limit=min(limit, 10))
    return await _read(ctx, source, records, query)


async def query_sql(ctx: RunContext[RunDeps], source: str, sql: str) -> str:
    """Run one read-only SELECT on a SQL source. Cite rows you use as [src:<id>]."""
    src = _source(ctx.deps, source)
    if src.kind != "sql":
        raise ValueError(f"{source} is not a SQL source")
    records = await src.query(sql)  # type: ignore[attr-defined]
    return await _read(ctx, source, records, sql)


async def _media_profile(deps: RunDeps, capability: Capability, prefer: str):
    if deps.router is None:
        raise RuntimeError("no model router configured")
    return deps.router.pick(capability, prefer=prefer)  # type: ignore[arg-type]


async def generate_image(
    ctx: RunContext[RunDeps], prompt: str, path: str, size: str = "1024x1024", prefer: str = "cheap"
) -> str:
    """Generate an image with the best available image model and save it in the workspace."""
    deps = ctx.deps
    profile = await _media_profile(deps, Capability.IMAGE_GEN, prefer)
    data = await media.generate_image(profile, prompt, size, meter=deps.meter)
    await deps.sandbox.write_file(path, data)
    deps.artifacts.append(path)
    return f"saved {path} ({len(data)} bytes) using {profile.name}"


async def text_to_speech(
    ctx: RunContext[RunDeps], text: str, path: str, voice: str | None = None, prefer: str = "cheap"
) -> str:
    """Turn text into speech audio (wav) with the best available voice model and save it."""
    deps = ctx.deps
    profile = await _media_profile(deps, Capability.TTS, prefer)
    data = await media.speak(profile, text, voice, meter=deps.meter)
    await deps.sandbox.write_file(path, data)
    deps.artifacts.append(path)
    return f"saved {path} ({len(data)} bytes) using {profile.name}"


async def transcribe_audio(ctx: RunContext[RunDeps], path: str) -> str:
    """Transcribe an audio file from the workspace to text."""
    deps = ctx.deps
    profile = await _media_profile(deps, Capability.STT, "cheap")
    return await media.transcribe(profile, await deps.sandbox.read_file(path), meter=deps.meter)


def knowledge_toolset() -> FunctionToolset[RunDeps]:
    return FunctionToolset([list_sources, search_knowledge, query_sql], id="knowledge")


def media_toolset() -> FunctionToolset[RunDeps]:
    return FunctionToolset([generate_image, text_to_speech, transcribe_audio], id="media")


def approval_id() -> str:
    return new_id()[:16]


def summarize_args(args: dict[str, Any], limit: int = 300) -> str:
    text = ", ".join(f"{k}={v!r}" for k, v in args.items())
    return text if len(text) <= limit else text[:limit] + "…"
