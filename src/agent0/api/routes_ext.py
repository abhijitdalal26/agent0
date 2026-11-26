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
from agent0.core.types import Capability, RunStatus, new_id, utcnow

router = APIRouter()


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


# Policy.decide's static defaults, mirrored so the dashboard shows the permission a tool
# gets when the agent sets no override. "shell" is listed as safe because workspace commands
# are; riskier commands still escalate per-call.
_DEFAULT_SAFE_TOOLS = {
    "shell",
    "read_file",
    "write_file",
    "list_files",
    "web_fetch",
    "load_skill",
    "read_skill_file",
}


def _tool_permission(name: str, overrides: dict[str, str]) -> str:
    if name in overrides:
        return overrides[name]
    return "safe" if name in _DEFAULT_SAFE_TOOLS else "needs_approval"


async def _agent_out(deps: ApiDeps, agent: AgentDef) -> dict[str, Any]:
    week_ago = utcnow() - timedelta(days=7)
    runs = [
        r
        for r in await deps.repos.runs.list(limit=MAX_SCAN)
        if r.agent == agent.name and r.started_at >= week_ago
    ]
    done = [r for r in runs if r.status in {RunStatus.SUCCEEDED, RunStatus.FAILED}]
    policy_tools = agent.policy.get("tools") or {}
    names = list(dict.fromkeys([*agent.tools, *policy_tools]))
    return {
        "name": agent.name,
        "description": agent.description,
        "instructions": agent.instructions,
        "capability": str(agent.capability),
        "prefer": agent.prefer,
        "model_profile": agent.model_profile,
        "tools": [{"name": n, "permission": _tool_permission(n, policy_tools)} for n in names],
        "skills": agent.skills,
        "mcp": agent.mcp,
        "policy": agent.policy,
        "budget": agent.budget,
        "budgets": agent.budget,
        "version": deps.agents.version(agent.name),
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
    row = await deps.repos.agents.get(name)
    if row and row.get("versions"):
        items = row["versions"]
    else:
        items = [
            {
                "version": 1,
                "updated_at": None,
                "author": str(agent.source) if agent.source else "file",
            }
        ]
    return {"items": items, "next_cursor": None}


_NAME_RE = r"^[a-z0-9][a-z0-9_-]{0,63}$"


class AgentToolIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    permission: Literal["safe", "needs_approval", "forbidden"] = "safe"


class AgentBudgetsIn(BaseModel):
    max_usd: float | None = Field(default=None, gt=0)
    max_steps: int | None = Field(default=None, gt=0, le=100_000)


class AgentIn(BaseModel):
    name: str | None = Field(default=None, pattern=_NAME_RE)
    description: str | None = None
    instructions: str | None = None
    model_profile: str | None = None
    tools: list[AgentToolIn | str] | None = None
    budgets: AgentBudgetsIn | None = None


class AgentCreate(BaseModel):
    name: str = Field(pattern=_NAME_RE)
    description: str = ""
    instructions: str = Field(min_length=1, max_length=100_000)
    model_profile: str | None = None
    tools: list[AgentToolIn | str] | None = None
    budgets: AgentBudgetsIn | None = None


def _check_profile(deps: ApiDeps, pin: str | None) -> str | None:
    if not pin:
        return None
    try:
        profile = deps.registry.get(pin)
    except KeyError:
        raise ApiError(422, "unknown_profile", f"unknown model profile {pin!r}") from None
    if profile.capability != Capability.CHAT:
        raise ApiError(422, "wrong_capability", f"profile {pin!r} is not a chat model")
    return pin


def _apply_agent_fields(agent: AgentDef, body: AgentIn | AgentCreate, deps: ApiDeps) -> AgentDef:
    fields: dict[str, Any] = {}
    if body.description is not None:
        fields["description"] = body.description
    if body.instructions is not None:
        if not body.instructions.strip():
            raise ApiError(422, "validation_error", "instructions cannot be empty")
        fields["instructions"] = body.instructions
    if body.model_profile is not None:
        fields["model_profile"] = _check_profile(deps, body.model_profile or None)
    policy = dict(agent.policy)
    if body.tools is not None:
        names: list[str] = []
        perms: dict[str, str] = {}
        for t in body.tools:
            tname = t if isinstance(t, str) else t.name
            perm = "safe" if isinstance(t, str) else t.permission
            if tname not in perms:
                names.append(tname)
            perms[tname] = perm
        fields["tools"] = names
        policy["tools"] = perms
    if body.budgets is not None:
        budget = dict(agent.budget)
        if body.budgets.max_usd is not None:
            budget["max_usd"] = body.budgets.max_usd
        if body.budgets.max_steps is not None:
            budget["max_steps"] = body.budgets.max_steps
        fields["budget"] = budget
    if policy != agent.policy:
        fields["policy"] = policy
    return agent.model_copy(update=fields)


async def _persist_agent(deps: ApiDeps, agent: AgentDef, version: int) -> None:
    row = await deps.repos.agents.get(agent.name)
    history = list(row["versions"]) if row and row.get("versions") else []
    if not history and version > 1:
        # Whatever shipped before the first DB save counts as v1.
        author = str(agent.source) if agent.source else "file"
        history = [{"version": 1, "updated_at": None, "author": author}]
    history = [
        *history,
        {"version": version, "updated_at": utcnow().isoformat(), "author": "dashboard"},
    ]
    definition = agent.model_dump(mode="json", exclude={"source"})
    await deps.repos.agents.upsert(agent.name, definition, version, history)
    deps.agents.upsert(agent, version)


@router.post("/agents", status_code=201)
async def create_agent(body: AgentCreate, deps: Deps) -> dict[str, Any]:
    if body.name in deps.agents:
        raise ApiError(409, "conflict", f"agent {body.name!r} already exists")
    base = AgentDef(name=body.name, description=body.description or "", instructions=body.instructions)
    agent = _apply_agent_fields(base, body, deps)
    await _persist_agent(deps, agent, version=1)
    return await _agent_out(deps, agent)


@router.put("/agents/{name}")
async def update_agent(name: str, body: AgentIn, deps: Deps) -> dict[str, Any]:
    if body.name and body.name != name:
        raise ApiError(422, "validation_error", "agent name cannot be changed")
    agent = _apply_agent_fields(_agent(deps, name), body, deps)
    await _persist_agent(deps, agent, version=deps.agents.version(name) + 1)
    return await _agent_out(deps, agent)


class FactEdit(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


def _fact(row: dict[str, Any]) -> dict[str, Any]:
    return {
        **row,
        "valid_from": iso(row.get("valid_from")),
        "valid_to": iso(row.get("valid_to")),
        "current": row.get("valid_to") is None,
    }


def _memory_store(deps: ApiDeps):
    from agent0.memory.pg import PgMemoryStore

    return PgMemoryStore(deps.repos.pool)


@router.get("/memory")
async def list_memory(
    deps: Deps,
    scope: str | None = None,
    scope_id: str | None = None,
    include_expired: bool = False,
    limit: Limit = 100,
    cursor: Cursor = None,
) -> dict[str, Any]:
    rows = await deps.repos.facts.list(scope, scope_id, include_expired, MAX_SCAN)
    return paginate(rows, limit, cursor, _fact)


@router.get("/memory/search")
async def search_memory(deps: Deps, q: str) -> dict[str, Any]:
    return {"items": [_fact(r) for r in await deps.repos.facts.search(q)], "next_cursor": None}


async def _get_fact(deps: ApiDeps, fact_id: str) -> dict[str, Any]:
    row = await deps.repos.facts.get(fact_id)
    if row is None:
        raise ApiError(404, "not_found", "fact not found")
    return row


@router.get("/memory/{fact_id}")
async def get_memory(deps: Deps, fact_id: str) -> dict[str, Any]:
    return _fact(await _get_fact(deps, fact_id))


@router.put("/memory/{fact_id}")
async def edit_memory(deps: Deps, fact_id: str, body: FactEdit) -> dict[str, Any]:
    from agent0.memory.base import Fact

    old = await _get_fact(deps, fact_id)
    if old["valid_to"] is not None:
        raise ApiError(409, "expired", "only current facts can be edited")
    new = Fact(scope=old["scope"], scope_id=old["scope_id"], content=body.content, source_id="dashboard")
    await _memory_store(deps).apply(new, "changes", fact_id)
    return _fact(await _get_fact(deps, new.id))


@router.delete("/memory/{fact_id}", status_code=204)
async def forget_memory(deps: Deps, fact_id: str) -> None:
    from agent0.memory.base import Fact

    old = await _get_fact(deps, fact_id)
    if old["valid_to"] is None:
        # Facts are expired, never deleted, so the audit trail survives.
        await _memory_store(deps).apply(Fact(content=old["content"]), "ends", fact_id)


@router.get("/memory/{fact_id}/revisions")
async def memory_revisions(deps: Deps, fact_id: str) -> dict[str, Any]:
    await _get_fact(deps, fact_id)
    return {"items": [_fact(r) for r in await deps.repos.facts.history(fact_id)], "next_cursor": None}


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
