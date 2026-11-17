from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import Any, Protocol

from cryptography.fernet import Fernet, InvalidToken
from psycopg_pool import AsyncConnectionPool

from agent0.core.types import utcnow
from agent0.models.base import ModelProfile

log = logging.getLogger(__name__)

TELEGRAM_SECRET = "AGENT0_TELEGRAM_BOT_TOKEN"


class SecretsDisabled(RuntimeError):
    pass


def generate_key() -> str:
    return Fernet.generate_key().decode()


def allowed_secret_names(profiles: Iterable[ModelProfile]) -> list[str]:
    return sorted({p.key_env for p in profiles} | {TELEGRAM_SECRET})


def _last4(value: str) -> str:
    # A suffix of a short value would reveal most of it.
    return value[-4:] if len(value) >= 12 else ""


class SecretStore(Protocol):
    @property
    def enabled(self) -> bool: ...
    async def load(self) -> None: ...
    async def set(self, name: str, value: str, by: str) -> None: ...
    async def delete(self, name: str) -> bool: ...
    async def list(self) -> list[dict[str, Any]]: ...
    async def get(self, name: str) -> str | None: ...
    def resolve(self, name: str) -> str | None: ...


class _BaseSecretStore(ABC):
    def __init__(self, master_key: str | None) -> None:
        self._fernet: Fernet | None = None
        if master_key:
            try:
                self._fernet = Fernet(master_key)
            except ValueError:
                log.error("AGENT0_SECRET_KEY is not a valid Fernet key; secret storage disabled")
        # Plaintext lives only in process memory so the sync key resolver needs no I/O.
        self._cache: dict[str, str] = {}

    @property
    def enabled(self) -> bool:
        return self._fernet is not None

    def _cipher(self) -> Fernet:
        if self._fernet is None:
            raise SecretsDisabled("AGENT0_SECRET_KEY is not set; the secret store is disabled")
        return self._fernet

    @abstractmethod
    async def _put(self, name: str, ciphertext: bytes, last4: str, by: str) -> None: ...

    @abstractmethod
    async def _drop(self, name: str) -> bool: ...

    @abstractmethod
    async def _rows(self) -> list[dict[str, Any]]: ...

    async def load(self) -> None:
        self._cache = {}
        if self._fernet is None:
            return
        for row in await self._rows():
            try:
                self._cache[row["name"]] = self._fernet.decrypt(bytes(row["ciphertext"])).decode()
            except InvalidToken:
                log.warning("secret %s cannot be decrypted with the current master key", row["name"])

    async def set(self, name: str, value: str, by: str) -> None:
        cipher = self._cipher()
        await self._put(name, cipher.encrypt(value.encode()), _last4(value), by)
        self._cache[name] = value

    async def delete(self, name: str) -> bool:
        self._cache.pop(name, None)
        return await self._drop(name)

    async def list(self) -> list[dict[str, Any]]:
        return [
            {"name": r["name"], "last4": r["last4"], "updated_at": r["updated_at"], "configured": True}
            for r in sorted(await self._rows(), key=lambda r: r["name"])
        ]

    async def get(self, name: str) -> str | None:
        if name not in self._cache:
            await self.load()
        return self._cache.get(name)

    def resolve(self, name: str) -> str | None:
        return self._cache.get(name)


class InMemorySecretStore(_BaseSecretStore):
    def __init__(self, master_key: str | None) -> None:
        super().__init__(master_key)
        self._data: dict[str, dict[str, Any]] = {}

    async def _put(self, name: str, ciphertext: bytes, last4: str, by: str) -> None:
        self._data[name] = {
            "name": name,
            "ciphertext": ciphertext,
            "last4": last4,
            "updated_at": utcnow(),
            "updated_by": by,
        }

    async def _drop(self, name: str) -> bool:
        return self._data.pop(name, None) is not None

    async def _rows(self) -> list[dict[str, Any]]:
        return list(self._data.values())


class PgSecretStore(_BaseSecretStore):
    def __init__(self, pool: AsyncConnectionPool, master_key: str | None) -> None:
        super().__init__(master_key)
        self.pool = pool

    async def _put(self, name: str, ciphertext: bytes, last4: str, by: str) -> None:
        async with self.pool.connection() as conn:
            await conn.execute(
                "INSERT INTO secrets (name, ciphertext, last4, updated_at, updated_by)"
                " VALUES (%s,%s,%s,now(),%s) ON CONFLICT (name) DO UPDATE SET"
                " ciphertext = EXCLUDED.ciphertext, last4 = EXCLUDED.last4,"
                " updated_at = now(), updated_by = EXCLUDED.updated_by",
                (name, ciphertext, last4, by),
            )

    async def _drop(self, name: str) -> bool:
        async with self.pool.connection() as conn:
            cur = await conn.execute("DELETE FROM secrets WHERE name = %s", (name,))
            return cur.rowcount > 0

    async def _rows(self) -> list[dict[str, Any]]:
        async with self.pool.connection() as conn:
            cur = await conn.execute("SELECT name, ciphertext, last4, updated_at, updated_by FROM secrets")
            return list(await cur.fetchall())
