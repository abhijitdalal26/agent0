from __future__ import annotations

import os
from collections.abc import Callable, Sequence

from pydantic_ai.models import Model
from pydantic_ai.models.fallback import FallbackModel
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.models.groq import GroqModel
from pydantic_ai.providers.google import GoogleProvider
from pydantic_ai.providers.groq import GroqProvider

from agent0.models.base import ModelProfile


class MissingKeyError(RuntimeError):
    pass


def api_key(profile: ModelProfile) -> str:
    key = os.environ.get(profile.key_env)
    if not key:
        raise MissingKeyError(f"environment variable {profile.key_env} is not set for {profile.name}")
    return key


# Adding a chat provider = one entry here.
CHAT_BUILDERS: dict[str, Callable[[ModelProfile, str], Model]] = {
    "groq": lambda p, key: GroqModel(p.model, provider=GroqProvider(api_key=key)),
    "google": lambda p, key: GoogleModel(p.model, provider=GoogleProvider(api_key=key)),
}


def build_model(profile: ModelProfile) -> Model:
    try:
        builder = CHAT_BUILDERS[profile.provider]
    except KeyError:
        raise ValueError(f"no chat builder for provider {profile.provider!r}") from None
    return builder(profile, api_key(profile))


def build_fallback(profiles: Sequence[ModelProfile]) -> Model:
    if not profiles:
        raise ValueError("build_fallback needs at least one profile")
    models = [build_model(p) for p in profiles]
    return models[0] if len(models) == 1 else FallbackModel(*models)
