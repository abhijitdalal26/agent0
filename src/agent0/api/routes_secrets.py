from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from agent0.api.deps import ApiDeps, Deps
from agent0.api.errors import ApiError
from agent0.api.shapes import iso
from agent0.models.registry import resolve_secret
from agent0.secrets import SecretsDisabled, allowed_secret_names

audit = logging.getLogger("agent0.audit")


def _limit(request: Request) -> None:
    request.app.state.secrets_limiter.check(request.client.host if request.client else "unknown")


router = APIRouter(prefix="/secrets", dependencies=[Depends(_limit)])


def _allowed(deps: ApiDeps, name: str) -> None:
    if name not in allowed_secret_names(deps.registry.all()):
        raise ApiError(422, "unknown_secret", f"{name} is not a recognised secret name")


async def _item(deps: ApiDeps, name: str) -> dict[str, Any]:
    stored = {r["name"]: r for r in await deps.secrets.list()}.get(name)
    if os.environ.get(name):
        return {"name": name, "last4": None, "configured": True, "source": "env", "updated_at": None}
    if stored:
        return {
            "name": name,
            "last4": stored["last4"] or None,
            "configured": True,
            "source": "store",
            "updated_at": iso(stored["updated_at"]),
        }
    return {"name": name, "last4": None, "configured": False, "source": None, "updated_at": None}


@router.get("")
async def list_secrets(deps: Deps) -> dict[str, Any]:
    names = allowed_secret_names(deps.registry.all())
    return {"items": [await _item(deps, n) for n in names], "next_cursor": None}


class SecretIn(BaseModel):
    value: str = Field(min_length=1, max_length=4096)


def _guard_env(name: str) -> None:
    if os.environ.get(name):
        raise ApiError(409, "env_managed", f"{name} is set in the environment and is read-only here")


@router.put("/{name}")
async def put_secret(name: str, body: SecretIn, deps: Deps) -> dict[str, Any]:
    _allowed(deps, name)
    _guard_env(name)
    value = body.value.strip()
    if not value or any(c in value for c in "\r\n\x00"):
        raise ApiError(422, "validation_error", "value must be a single non-empty line")
    try:
        await deps.secrets.set(name, value, "dashboard")
    except SecretsDisabled as exc:
        raise ApiError(503, "secrets_disabled", str(exc)) from None
    audit.info("secret.set name=%s by=dashboard", name)
    return await _item(deps, name)


@router.delete("/{name}")
async def delete_secret(name: str, deps: Deps) -> dict[str, Any]:
    _allowed(deps, name)
    _guard_env(name)
    if not await deps.secrets.delete(name):
        raise ApiError(404, "not_found", f"{name} is not stored")
    audit.info("secret.delete name=%s by=dashboard", name)
    return await _item(deps, name)


@router.post("/{name}/test")
async def test_secret(name: str, deps: Deps) -> dict[str, Any]:
    _allowed(deps, name)
    value = resolve_secret(name)
    if not value:
        raise ApiError(409, "not_configured", f"{name} is not configured")
    if deps.secret_tester is None:
        raise ApiError(501, "not_implemented", "no secret tester configured")
    provider = next((p.provider for p in deps.registry.all() if p.key_env == name), None)
    try:
        ok, message = await deps.secret_tester(name, value, provider)
    except Exception as exc:
        ok, message = False, f"test failed: {type(exc).__name__}"
    return {"ok": ok, "message": message.replace(value, "***")}
