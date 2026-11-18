from __future__ import annotations

import asyncio
import sys
from collections.abc import Coroutine
from typing import Any

import typer
from rich.console import Console

app = typer.Typer(no_args_is_help=True, help="agent0: a multi-model agent harness that verifies its work.")
console = Console()


def _run_async(coro: Coroutine[Any, Any, None]) -> None:
    # psycopg async needs a selector loop; Windows defaults to Proactor.
    if sys.platform == "win32":
        asyncio.run(coro, loop_factory=asyncio.SelectorEventLoop)
    else:
        asyncio.run(coro)


async def _load_stored_secrets() -> None:
    # Keys added in the dashboard live encrypted in Postgres; without a DB, env vars alone are fine.
    from psycopg.rows import dict_row
    from psycopg_pool import AsyncConnectionPool

    from agent0.config import get_settings
    from agent0.secrets.store import PgSecretStore

    settings = get_settings()
    if not settings.secret_key:
        return
    pool = AsyncConnectionPool(
        settings.database_url, min_size=1, max_size=1, open=False, kwargs={"row_factory": dict_row}
    )
    try:
        await pool.open(wait=True, timeout=3)
        store = PgSecretStore(pool, settings.secret_key)  # type: ignore[arg-type]
        await store.load()
        from agent0.models.registry import set_secret_resolver

        set_secret_resolver(store.resolve)
    except Exception:
        return
    finally:
        await pool.close()


@app.callback()
def _load_env() -> None:
    from dotenv import load_dotenv

    load_dotenv(".env", override=False)
    # Windows consoles default to cp1252, which can't print model output like "→".
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]


@app.command()
def version() -> None:
    from importlib.metadata import version as v

    typer.echo(v("agent0"))


@app.command()
def run(
    prompt: str = typer.Argument(None, help="What to do. Omit when using --task-file."),
    task_file: str = typer.Option(None, help="JSON with title, prompt, agent and required criteria."),
    agent: str = typer.Option("executor", help="Agent name from agents/ or plugins."),
    retries: int = typer.Option(2, help="Retries after a failed verification."),
    max_usd: float = typer.Option(1.0, help="Spend cap for this task."),
    sandbox: str = typer.Option(None, help="docker | local (default from settings)."),
) -> None:
    """Run one task in this process and stream what happens. Approvals are asked in the terminal."""
    import json

    spec = json.loads(open(task_file, encoding="utf-8").read()) if task_file else {}
    prompt = prompt or spec.get("prompt") or ""
    if not prompt:
        raise typer.BadParameter("give a prompt or --task-file")
    from agent0.models.base import NoProfileAvailable

    try:
        _run_async(_run(prompt, spec.get("agent", agent), retries, max_usd, sandbox, spec))
    except NoProfileAvailable as e:
        console.print(f"[red]No model available:[/red] {e}. Set provider keys in .env, then `agent0 models`.")
        raise typer.Exit(1) from None


async def _run(
    prompt: str, agent: str, retries: int, max_usd: float, sandbox: str | None, spec: dict | None = None
) -> None:
    from agent0.config import get_settings
    from agent0.core.events import MemoryEventSink
    from agent0.core.types import Budget, Task
    from agent0.orchestrator.local import LocalOrchestrator, final_message
    from agent0.orchestrator.runtime import build_runtime

    await _load_stored_secrets()
    settings = get_settings()
    if sandbox:
        settings = settings.model_copy(update={"sandbox": sandbox})
    sink = MemoryEventSink()
    rt = build_runtime(settings, events=sink)
    orch = LocalOrchestrator(rt)

    async def ask(chat_id, run_id, approval_id, question):
        answer = await asyncio.to_thread(
            console.input, f"\n[bold yellow]Approval needed[/] {question}\napprove? [y/N] "
        )
        await orch.decide_approval(
            approval_id, "approve" if answer.strip().lower() == "y" else "reject", "cli"
        )

    rt.notify_approval = ask
    queue = sink.subscribe()
    task = Task(
        title=(spec or {}).get("title", prompt[:80]),
        prompt=prompt,
        criteria=(spec or {}).get("criteria", []),
        agent=agent,
        source="cli",
        budget=Budget(max_retries=retries, max_usd=max_usd),
    )
    run = await orch.submit(task)
    job = orch.running[run.id]
    console.print(f"[dim]run {run.id} · workspace {settings.workspace_root / run.id}[/]")
    while not (job.done() and queue.empty()):
        try:
            event = await asyncio.wait_for(queue.get(), timeout=0.5)
        except TimeoutError:
            continue
        console.print(f"[cyan]{event.type.value:<20}[/] {_brief(event.payload)}")
    console.print()
    console.print(final_message(task, run.id, job.result()))


def _brief(payload: dict) -> str:
    keys = (
        "title",
        "goal",
        "tool",
        "args",
        "check_id",
        "status",
        "evidence",
        "profile",
        "cost_usd",
        "message",
        "reason",
        "question",
        "name",
        "ids",
    )
    if "message" in payload or "evidence" in payload:
        return " ".join(f"{k}={str(payload[k])[:2000]}" for k in keys if k in payload)
    parts = [f"{k}={str(payload[k])[:120]}" for k in keys if k in payload]
    return " ".join(parts)[:300]


@app.command()
def serve(host: str = typer.Option(None), port: int = typer.Option(None), reload: bool = False) -> None:
    """API for the dashboard + Telegram bot + orchestrator (local or temporal, from AGENT0_ORCHESTRATOR)."""
    import uvicorn

    from agent0.config import get_settings

    s = get_settings()
    config = uvicorn.Config(
        "agent0.serve:app_factory",
        factory=True,
        host=host or s.api_host,
        port=port or s.api_port,
        reload=reload,
    )
    if reload:
        uvicorn.Server(config).run()
    else:
        _run_async(uvicorn.Server(config).serve())


@app.command()
def worker() -> None:
    """Temporal worker that executes durable runs (use with AGENT0_ORCHESTRATOR=temporal)."""
    from agent0.serve import worker as run

    _run_async(run())


@app.command("db-init")
def db_init() -> None:
    """Create or update the Postgres schema."""

    async def go() -> None:
        from agent0.db.pool import apply_schema, close_pool, create_pool

        pool = await create_pool()
        try:
            await apply_schema(pool)
        finally:
            await close_pool(pool)

    _run_async(go())
    console.print("schema applied")


@app.command("ingest")
def ingest(source: str) -> None:
    """Index a docs knowledge source from config/knowledge.yaml into Postgres."""

    async def go() -> None:
        from agent0.config import get_settings
        from agent0.db.pool import close_pool, create_pool
        from agent0.knowledge.registry import load_sources

        s = get_settings()
        pool = await create_pool(s)
        try:
            src = load_sources(s.config_dir / "knowledge.yaml", pool=pool)[source]
            console.print(f"{await src.ingest()} chunks indexed")  # type: ignore[attr-defined]
        finally:
            await close_pool(pool)

    _run_async(go())


@app.command("secrets-keygen")
def secrets_keygen() -> None:
    """Print a new master key for AGENT0_SECRET_KEY (encrypts API keys stored from the dashboard)."""
    from agent0.secrets import generate_key

    typer.echo(generate_key())


@app.command()
def models() -> None:
    """Show model profiles and which ones have a key configured."""
    from agent0.config import get_settings
    from agent0.models.registry import ModelRegistry

    _run_async(_load_stored_secrets())
    reg = ModelRegistry.load(get_settings().config_dir / "models.yaml")
    ok = {p.name for p in reg.available()}
    for p in reg.all():
        mark = "[green]ready[/]" if p.name in ok else f"[red]missing {p.key_env}[/]"
        console.print(f"{p.capability.value:<10} {p.name:<16} {p.provider}:{p.model:<36} {mark}")
