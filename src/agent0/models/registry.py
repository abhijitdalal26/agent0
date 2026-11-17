from __future__ import annotations

import os
from pathlib import Path

import yaml

from agent0.core.types import Capability
from agent0.models.base import ModelProfile


class ModelRegistry:
    def __init__(self, profiles: list[ModelProfile] | None = None) -> None:
        self._profiles: dict[str, ModelProfile] = {}
        for p in profiles or []:
            self.add(p)

    @classmethod
    def load(cls, path: str | Path) -> ModelRegistry:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        return cls([ModelProfile.model_validate(p) for p in data.get("profiles", [])])

    def all(self) -> list[ModelProfile]:
        return list(self._profiles.values())

    def get(self, name: str) -> ModelProfile:
        try:
            return self._profiles[name]
        except KeyError:
            raise KeyError(f"unknown model profile: {name}") from None

    def available(self, capability: Capability | None = None) -> list[ModelProfile]:
        return [
            p
            for p in self._profiles.values()
            if p.enabled and os.environ.get(p.key_env) and (capability is None or p.capability == capability)
        ]

    def add(self, profile: ModelProfile) -> None:
        if profile.name in self._profiles:
            raise ValueError(f"profile already exists: {profile.name}")
        self._profiles[profile.name] = profile

    def update(self, profile: ModelProfile) -> None:
        self.get(profile.name)
        self._profiles[profile.name] = profile

    def remove(self, name: str) -> None:
        self.get(name)
        del self._profiles[name]
