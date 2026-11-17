from __future__ import annotations

import asyncio
import contextlib
import logging
from pathlib import Path
from typing import Any

from fastapi import FastAPI

from agent0.api.app import create_app
from agent0.api.deps import ApiDeps
from agent0.api.testers import default_tester
from agent0.channels.base import ApprovalRequest, InboundTask, OutboundMessage
from agent0.config import Settings, get_settings
from agent0.core.types import RunStatus, Task
from agent0.db.pool import apply_schema, close_pool, create_pool
from agent0.db.repos import PgEventSink
from agent0.models.registry import resolve_secret, set_secret_resolver
from agent0.orchestrator.runtime import Runtime, build_runtime
from agent0.secrets import PgSecretStore

log = logging.getLogger("agent0")

TELEGRAM_KEY = "AGENT0_TELEGRAM_BOT_TOKEN"


def telegram_channel(settings: Settings, **handlers: Any):
    token = settings.telegram_bot_token or resolve_secret(TELEGRAM_KEY)
    if not token:
        return None
    from agent0.channels.telegram import TelegramChannel

    return TelegramChannel(settings.model_copy(update={"telegram_bot_token": token}), **handlers)


def wire_notifications(rt: Runtime, channel) -> None:
    if channel is None:
        return

    async def notify(chat_id: str | None, text: str, attachments: list[str]) -> None:
        if chat_id:
            await channel.send(OutboundMessage(chat_id=chat_id, text=text, attachments=attachments))

    async def notify_approval(chat_id: str | None, run_id: str, approval_id: str, question: str) -> None:
        if chat_id:
            await channel.request_approval(
                ApprovalRequest(approval_id=approval_id, run_id=run_id, chat_id=chat_id, question=question)
            )

    rt.notify, rt.notify_approval = notify, notify_approval


async def make_orchestrator(rt: Runtime):
    if rt.settings.orchestrator == "temporal":
        from agent0.orchestrator.temporal import TemporalOrchestrator, connect

        return TemporalOrchestrator(rt, await connect(rt.settings))
    from agent0.orchestrator.local import LocalOrchestrator

    return LocalOrchestrator(rt)


async def load_secrets(pool, settings: Settings) -> PgSecretStore:
    secrets = PgSecretStore(pool, settings.secret_key)
    await secrets.load()
    set_secret_resolver(secrets.resolve)
    return secrets


async def build_deps() -> ApiDeps:
    settings = get_settings()
    pool = await create_pool(settings)
    await apply_schema(pool)
    secrets = await load_secrets(pool, settings)
    rt = build_runtime(settings, pool=pool)
    orchestrator = await make_orchestrator(rt)

    async def on_task(msg: InboundTask) -> str:
        task = Task(title=msg.text[:80], prompt=msg.text, source="telegram", chat_id=msg.chat_id)
        await rt.repos.tasks.create(task)
        run = await orchestrator.submit(task)
        return run.id

    async def on_approval(approval_id: str, decision: str, user: str) -> None:
        await orchestrator.decide_approval(approval_id, decision, f"telegram:{user}", None)

    async def status() -> str:
        active = [
            s.value for s in RunStatus if s not in (RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.STOPPED)
        ]
        runs = [r for s in active for r in await rt.repos.runs.list(status=s, limit=10)]
        if not runs:
            return "Nothing running."
        return "\n".join(f"{r.id[:8]} {r.status} {r.current_step or ''} ${r.cost_usd:.4f}" for r in runs)

    async def stop(run_id: str) -> str:
        matches = [r for r in await rt.repos.runs.list(limit=200) if r.id.startswith(run_id)]
        if len(matches) != 1:
            return "No unique run with that id."
        await orchestrator.stop(matches[0].id)
        return f"Stopping {matches[0].id}"

    channel = telegram_channel(settings, status_handler=status, stop_handler=stop)
    wire_notifications(rt, channel)
    poller = asyncio.create_task(channel.start(on_task, on_approval)) if channel else None
    if channel is None:
        log.warning("Telegram disabled: no %s in env or secret store", TELEGRAM_KEY)

    async def close() -> None:
        if channel is not None:
            await channel.stop()
            if poller is not None:
                poller.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await poller
        await close_pool(pool)

    return ApiDeps(
        repos=rt.repos,
        orchestrator=orchestrator,
        registry=rt.registry,
        router=rt.router,
        secrets=secrets,
        skills=rt.skills,
        mcp=rt.mcp,
        plugins=rt.plugins,
        agents=rt.agents,
        event_stream=PgEventSink(pool),
        settings=settings,
        secret_tester=default_tester,
        close=close,
    )


def app_factory() -> FastAPI:
    """uvicorn agent0.serve:app_factory --factory"""
    from dotenv import load_dotenv

    load_dotenv(".env", override=False)
    return create_app(build_deps=build_deps)


async def worker() -> None:
    from agent0.orchestrator.temporal import connect, run_worker

    settings = get_settings()
    pool = await create_pool(settings)
    await apply_schema(pool)
    await load_secrets(pool, settings)
    rt = build_runtime(settings, pool=pool)
    wire_notifications(rt, telegram_channel(settings))
    try:
        await run_worker(rt, await connect(settings))
    finally:
        await close_pool(pool)


def workspace(settings: Settings, run_id: str) -> Path:
    return settings.workspace_root / run_id
