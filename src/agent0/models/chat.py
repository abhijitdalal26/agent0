from __future__ import annotations

from collections.abc import Callable, Sequence

from pydantic_ai.exceptions import ModelAPIError, OutputTokenLimitExceeded
from pydantic_ai.models import Model
from pydantic_ai.models.fallback import FallbackModel
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.models.groq import GroqModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.profiles import InlineDefsJsonSchemaTransformer
from pydantic_ai.profiles.openai import OpenAIModelProfile
from pydantic_ai.providers.google import GoogleProvider
from pydantic_ai.providers.groq import GroqProvider
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings

from agent0.models.base import ModelProfile
from agent0.models.registry import resolve_secret


class MissingKeyError(RuntimeError):
    pass


def api_key(profile: ModelProfile) -> str:
    key = resolve_secret(profile.key_env)
    if not key:
        raise MissingKeyError(
            f"key {profile.key_env} is not set (environment or secret store) for {profile.name}"
        )
    return key


DEFAULT_TIMEOUT_S = 90.0
DEFAULT_MAX_TOKENS = 8192


def _settings(p: ModelProfile) -> ModelSettings:
    # Without a timeout a provider that never answers hangs the run, and FallbackModel only moves on errors.
    # Provider default output limits are small enough that long files hit them before any text comes back.
    return ModelSettings(
        timeout=float(p.settings.get("timeout_s", DEFAULT_TIMEOUT_S)),
        max_tokens=int(p.settings.get("max_tokens", DEFAULT_MAX_TOKENS)),
    )


# Adding a chat provider = one entry here.
CHAT_BUILDERS: dict[str, Callable[[ModelProfile, str], Model]] = {
    "groq": lambda p, key: GroqModel(p.model, provider=GroqProvider(api_key=key), settings=_settings(p)),
    "google": lambda p, key: GoogleModel(
        p.model, provider=GoogleProvider(api_key=key), settings=_settings(p)
    ),
    "openai_compat": lambda p, key: OpenAIChatModel(
        p.model,
        provider=OpenAIProvider(base_url=p.settings["base_url"], api_key=key),
        # Brokers such as Gonka reject $defs/$ref in tool schemas.
        profile=OpenAIModelProfile(json_schema_transformer=InlineDefsJsonSchemaTransformer),
        settings=_settings(p),
    ),
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
    if len(models) == 1:
        return models[0]
    return FallbackModel(*models, fallback_on=(ModelAPIError, OutputTokenLimitExceeded))
