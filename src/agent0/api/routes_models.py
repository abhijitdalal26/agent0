from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Query
from pydantic import BaseModel

from agent0.api.deps import Deps
from agent0.api.errors import ApiError, paginate
from agent0.api.routes_core import MAX_SCAN, Cursor, Limit, _when
from agent0.api.shapes import iso, profile_out
from agent0.core.types import Capability
from agent0.models.base import Cost, ModelProfile, NoProfileAvailable

router = APIRouter()


def _capability(value: str | None) -> Capability | None:
    if value is None:
        return None
    try:
        return Capability(value)
    except ValueError:
        raise ApiError(422, "validation_error", f"unknown capability {value!r}") from None


async def _merged(deps: Any) -> dict[str, ModelProfile]:
    # DB rows are operator overrides and win over the YAML registry.
    merged = {p.name: p for p in deps.registry.all()}
    for p in await deps.repos.model_profiles.list():
        merged[p.name] = p
    return merged


async def _persist(deps: Any, profile: ModelProfile) -> None:
    await deps.repos.model_profiles.upsert(profile)
    try:
        deps.registry.update(profile)
    except KeyError:
        deps.registry.add(profile)


@router.get("/model-profiles")
async def list_profiles(
    deps: Deps, limit: Limit = 100, cursor: Cursor = None, capability: str | None = None
) -> dict[str, Any]:
    cap = _capability(capability)
    profiles = sorted((await _merged(deps)).values(), key=lambda p: p.name)
    profiles = [p for p in profiles if cap is None or p.capability == cap]
    return paginate(profiles, limit, cursor, profile_out)


@router.post("/model-profiles", status_code=201)
async def create_profile(body: ModelProfile, deps: Deps) -> dict[str, Any]:
    if body.name in await _merged(deps):
        raise ApiError(409, "conflict", f"profile {body.name} already exists")
    await _persist(deps, body)
    return profile_out(body)


class ProfileUpdate(BaseModel):
    provider: str | None = None
    model: str | None = None
    capability: Capability | None = None
    tags: list[str] | None = None
    cost: Cost | None = None
    context_window: int | None = None
    key_env: str | None = None
    enabled: bool | None = None
    settings: dict | None = None


@router.put("/model-profiles/{profile_id}")
async def update_profile(profile_id: str, body: ProfileUpdate, deps: Deps) -> dict[str, Any]:
    current = (await _merged(deps)).get(profile_id)
    if current is None:
        raise ApiError(404, "not_found", f"profile {profile_id} not found")
    updated = ModelProfile.model_validate({**current.model_dump(), **body.model_dump(exclude_unset=True)})
    await _persist(deps, updated)
    return profile_out(updated)


@router.delete("/model-profiles/{profile_id}", status_code=204)
async def delete_profile(profile_id: str, deps: Deps) -> None:
    if not await deps.repos.model_profiles.delete(profile_id):
        if profile_id in {p.name for p in deps.registry.all()}:
            raise ApiError(
                409, "builtin_profile", "profile comes from config/models.yaml; disable it instead"
            )
        raise ApiError(404, "not_found", f"profile {profile_id} not found")
    try:
        deps.registry.remove(profile_id)
    except KeyError:
        pass


@router.get("/router/preview")
async def router_preview(
    deps: Deps,
    capability: str,
    prefer: Annotated[str, Query(pattern="^(cheap|fast|smart)$")] = "cheap",
) -> dict[str, Any]:
    cap = _capability(capability)
    reason = deps.router.explain(cap, prefer)  # type: ignore[arg-type]
    try:
        profile = profile_out(deps.router.pick(cap, prefer))  # type: ignore[arg-type]
    except NoProfileAvailable:
        profile = None
    return {"profile": profile, "reason": reason}


@router.get("/usage")
async def list_usage(
    deps: Deps,
    limit: Limit = 100,
    cursor: Cursor = None,
    provider: str | None = None,
    capability: str | None = None,
    agent: str | None = None,
    from_: Annotated[str | None, Query(alias="from")] = None,
    to: str | None = None,
) -> dict[str, Any]:
    lister = getattr(deps.repos.usage, "list", None)
    if lister is None:
        raise ApiError(501, "not_implemented", "usage listing needs UsageRepo.list")
    rows = await lister(since=_when(from_, "from"), until=_when(to, "to"), limit=MAX_SCAN)
    rows = [
        r
        for r in rows
        if (provider is None or r["provider"] == provider)
        and (capability is None or r["capability"] == capability)
        and (agent is None or r.get("agent") == agent)
    ]

    def out(r: dict[str, Any]) -> dict[str, Any]:
        return {**r, "id": str(r["id"]), "created_at": iso(r.get("created_at"))}

    return paginate(rows, limit, cursor, out)


@router.get("/usage/summary")
async def usage_summary(
    deps: Deps,
    group_by: Annotated[str, Query(pattern="^(provider|capability|agent|day)$")] = "provider",
    from_: Annotated[str | None, Query(alias="from")] = None,
    to: str | None = None,
) -> dict[str, Any]:
    rows = await deps.repos.usage.summary([group_by], _when(from_, "from"), _when(to, "to"))
    return {"group_by": group_by, "items": rows}
