from __future__ import annotations

from datetime import timedelta
from typing import Any, Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from agent0.agents.definitions import AgentDef
from agent0.api.deps import ApiDeps, Deps
from agent0.api.errors import ApiError, paginate
from agent0.api.routes_core import MAX_SCAN, Cursor, Limit
from agent0.api.shapes import iso
from agent0.core.types import RunStatus, new_id, utcnow

router = APIRouter()


def _not_implemented(what: str) -> ApiError:
    return ApiError(501, "not_implemented", f"{what} is not available yet")


def _overrides(rows: list[dict[str, Any]]) -> dict[str, bool]:
    return {r["id"]: r["enabled"] for r in rows}


def _extensions(deps: ApiDeps, mcp_status: dict[str, str], enabled: dict[str, bool]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for name in deps.skills.names():
        skill = deps.skills.get(name)
        ext_id = f"skill:{name}"
        out.append(
            {
                "id": ext_id,
                "kind": "skill",
                "name": name,
                "description": skill.description,
                "enabled": enabled.get(ext_id, True),
                "config": {"path": str(skill.dir)},
            }
        )
    for name in deps.mcp.names():
        cfg = deps.mcp.servers[name]
        ext_id = f"mcp:{name}"
        out.append(
            {
                "id": ext_id,
                "kind": "mcp",
                "name": name,
                "description": cfg.description,
                "enabled": enabled.get(ext_id, True),
                "status": mcp_status.get(name, "idle"),
                # Only names of env/header entries: their values may be credentials.
                "config": {
                    "transport": cfg.transport,
                    "command": cfg.command,
                    "args": cfg.args,
                    "url": cfg.url,
                    "env_keys": sorted(cfg.env),
                    "header_names": sorted(cfg.headers),
                },
            }
        )
    for plugin in deps.plugins.discover():
        ext_id = f"plugin:{plugin.name}"
        out.append(
            {
                "id": ext_id,
                "kind": "plugin",
                "name": plugin.name,
                "description": plugin.description,
                "enabled": enabled.get(ext_id, plugin.enabled),
                "config": {
                    "version": plugin.version,
                    "checks": plugin.checks,
                    "has_skills": plugin.skills_dir.is_dir(),
                    "has_agents": plugin.agents_dir.is_dir(),
                    "has_mcp": plugin.mcp_file.is_file(),
                },
            }
        )
    return out


async def _all_extensions(request: Request, deps: ApiDeps) -> list[dict[str, Any]]:
    enabled = _overrides(await deps.repos.extensions.list())
    status = request.app.state.mcp_status
    return _extensions(deps, status, enabled)


async def _find(request: Request, deps: ApiDeps, ext_id: str) -> dict[str, Any]:
    for ext in await _all_extensions(request, deps):
        if ext["id"] == ext_id:
            return ext
    raise ApiError(404, "not_found", f"extension {ext_id} not found")


@router.get("/extensions")
async def list_extensions(
    request: Request,
    deps: Deps,
    limit: Limit = 100,
    cursor: Cursor = None,
    kind: Literal["skill", "mcp", "plugin"] | None = None,
) -> dict[str, Any]:
    items = [e for e in await _all_extensions(request, deps) if kind is None or e["kind"] == kind]
    return paginate(items, limit, cursor)


@router.get("/extensions/{ext_id}")
async def get_extension(ext_id: str, request: Request, deps: Deps) -> dict[str, Any]:
    ext = await _find(request, deps, ext_id)
    if ext["kind"] == "skill":
        try:
            ext["config"]["body"] = deps.skills.body(ext["name"])
        except Exception:
            ext["config"]["body"] = None
    return ext


class ExtensionUpdate(BaseModel):
    enabled: bool


@router.put("/extensions/{ext_id}")
async def update_extension(
    ext_id: str, body: ExtensionUpdate, request: Request, deps: Deps
) -> dict[str, Any]:
    ext = await _find(request, deps, ext_id)
    await deps.repos.extensions.upsert(ext_id, ext["kind"], ext["name"], ext["description"], body.enabled, {})
    return {**ext, "enabled": body.enabled}


@router.post("/extensions/{ext_id}/test")
async def test_extension(ext_id: str, request: Request, deps: Deps) -> dict[str, Any]:
    ext = await _find(request, deps, ext_id)
    if ext["kind"] != "mcp":
        raise ApiError(422, "validation_error", "only MCP servers can be tested")
    status = request.app.state.mcp_status
    try:
        tools = await deps.mcp.test_connection(ext["name"])
    except Exception as exc:
        status[ext["name"]] = "error"
        return {"ok": False, "tools": [], "error": f"{type(exc).__name__}: {str(exc)[:300]}"}
    status[ext["name"]] = "connected"
    return {"ok": True, "tools": tools, "error": None}


async def _agent_out(deps: ApiDeps, agent: AgentDef) -> dict[str, Any]:
    week_ago = utcnow() - timedelta(days=7)
    runs = [
        r
        for r in await deps.repos.runs.list(limit=MAX_SCAN)
        if r.agent == agent.name and r.started_at >= week_ago
    ]
    done = [r for r in runs if r.status in {RunStatus.SUCCEEDED, RunStatus.FAILED}]
    return {
        "name": agent.name,
        "description": agent.description,
        "instructions": agent.instructions,
        "capability": str(agent.capability),
        "prefer": agent.prefer,
        "model_profile": None,
        "tools": agent.tools,
        "skills": agent.skills,
        "mcp": agent.mcp,
        "policy": agent.policy,
        "budget": agent.budget,
        "version": 1,
        "runs_7d": len(runs),
        "success_rate": (sum(1 for r in done if r.status == RunStatus.SUCCEEDED) / len(done))
        if done
        else None,
        "avg_cost_usd": (sum(r.cost_usd for r in runs) / len(runs)) if runs else None,
    }


def _agent(deps: ApiDeps, name: str) -> AgentDef:
    if name not in deps.agents:
        raise ApiError(404, "not_found", f"agent {name} not found")
    return deps.agents.get(name)


@router.get("/agents")
async def list_agents(deps: Deps, limit: Limit = 100, cursor: Cursor = None) -> dict[str, Any]:
    page = paginate(deps.agents.all(), limit, cursor)
    return {"items": [await _agent_out(deps, a) for a in page["items"]], "next_cursor": page["next_cursor"]}


@router.get("/agents/{name}")
async def get_agent(name: str, deps: Deps) -> dict[str, Any]:
    return await _agent_out(deps, _agent(deps, name))


@router.get("/agents/{name}/versions")
async def agent_versions(name: str, deps: Deps) -> dict[str, Any]:
    agent = _agent(deps, name)
    return {
        "items": [{"version": 1, "instructions": agent.instructions, "source": str(agent.source)}],
        "next_cursor": None,
    }


@router.post("/agents", status_code=501)
async def create_agent() -> None:
    raise _not_implemented("creating agents")


@router.put("/agents/{name}")
async def update_agent(name: str) -> None:
    raise _not_implemented("editing agents")


@router.get("/memory")
async def list_memory(scope: str | None = None, scope_id: str | None = None) -> None:
    raise _not_implemented("memory documents")


@router.get("/memory/search")
async def search_memory(q: str) -> None:
    raise _not_implemented("memory search")


@router.api_route("/memory/{doc_id}", methods=["GET", "PUT", "DELETE"])
async def memory_doc(doc_id: str) -> None:
    raise _not_implemented("memory documents")


@router.get("/memory/{doc_id}/revisions")
async def memory_revisions(doc_id: str) -> None:
    raise _not_implemented("memory revisions")


class ScheduleIn(BaseModel):
    agent: str
    cron: str = Field(min_length=1, max_length=100)
    prompt: str = Field(min_length=1, max_length=50_000)
    enabled: bool = True


def _schedule_out(row: dict[str, Any]) -> dict[str, Any]:
    return {**row, "last_run_at": iso(row.get("last_run_at"))}


def _check_schedule(deps: ApiDeps, body: ScheduleIn) -> None:
    if body.agent not in deps.agents:
        raise ApiError(422, "unknown_agent", f"unknown agent {body.agent!r}")
    if len(body.cron.split()) != 5:
        raise ApiError(422, "invalid_cron", "cron must have 5 fields")


@router.get("/schedules")
async def list_schedules(deps: Deps, limit: Limit = 100, cursor: Cursor = None) -> dict[str, Any]:
    return paginate(await deps.repos.schedules.list(), limit, cursor, _schedule_out)


@router.post("/schedules", status_code=201)
async def create_schedule(body: ScheduleIn, deps: Deps) -> dict[str, Any]:
    _check_schedule(deps, body)
    sid = new_id()
    await deps.repos.schedules.upsert(sid, body.agent, body.cron, body.prompt, body.enabled)
    return _schedule_out(await deps.repos.schedules.get(sid))


@router.put("/schedules/{schedule_id}")
async def update_schedule(schedule_id: str, body: ScheduleIn, deps: Deps) -> dict[str, Any]:
    if await deps.repos.schedules.get(schedule_id) is None:
        raise ApiError(404, "not_found", f"schedule {schedule_id} not found")
    _check_schedule(deps, body)
    await deps.repos.schedules.upsert(schedule_id, body.agent, body.cron, body.prompt, body.enabled)
    return _schedule_out(await deps.repos.schedules.get(schedule_id))


@router.delete("/schedules/{schedule_id}", status_code=204)
async def delete_schedule(schedule_id: str, deps: Deps) -> None:
    if not await deps.repos.schedules.delete(schedule_id):
        raise ApiError(404, "not_found", f"schedule {schedule_id} not found")
