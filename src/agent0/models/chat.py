from __future__ import annotations

from collections.abc import AsyncGenerator, Callable, Sequence
from contextlib import asynccontextmanager
from typing import Any

from pydantic_ai.exceptions import ModelAPIError, ModelRateLimitError, OutputTokenLimitExceeded
from pydantic_ai.messages import ModelMessage, ModelResponse
from pydantic_ai.models import Model, ModelRequestParameters, StreamedResponse
from pydantic_ai.models.fallback import FallbackModel
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.models.groq import GroqModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.models.wrapper import WrapperModel
from pydantic_ai.profiles import InlineDefsJsonSchemaTransformer
from pydantic_ai.profiles.openai import OpenAIModelProfile
from pydantic_ai.providers.google import GoogleProvider
from pydantic_ai.providers.groq import GroqProvider
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings

from agent0.models.base import ModelProfile
from agent0.models.cooldown import CooldownTracker, default_tracker
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


class _CooldownModel(WrapperModel):
    """Records a rate-limit strike on the profile so the router demotes it
    until the cooldown expires, instead of every call re-picking a provider
    whose quota is exhausted."""

    def __init__(self, wrapped: Model, profile_name: str, tracker: CooldownTracker) -> None:
        super().__init__(wrapped)
        self._profile_name = profile_name
        self._tracker = tracker

    async def request(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
    ) -> ModelResponse:
        try:
            return await self.wrapped.request(messages, model_settings, model_request_parameters)
        except ModelRateLimitError as exc:
            self._tracker.record(self._profile_name, retry_after_s=exc.retry_after)
            raise

    @asynccontextmanager
    async def request_stream(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
        run_context: Any = None,
    ) -> AsyncGenerator[StreamedResponse]:
        try:
            async with self.wrapped.request_stream(
                messages, model_settings, model_request_parameters, run_context
            ) as response_stream:
                yield response_stream
        except ModelRateLimitError as exc:
            self._tracker.record(self._profile_name, retry_after_s=exc.retry_after)
            raise


def _maybe_wrap(model: Model, profile: ModelProfile, tracker: CooldownTracker | None) -> Model:
    if tracker is None:
        return model
    return _CooldownModel(model, profile.name, tracker)


def build_model(profile: ModelProfile, cooldowns: CooldownTracker | None = None) -> Model:
    try:
        builder = CHAT_BUILDERS[profile.provider]
    except KeyError:
        raise ValueError(f"no chat builder for provider {profile.provider!r}") from None
    model = builder(profile, api_key(profile))
    return _maybe_wrap(model, profile, cooldowns if cooldowns is not None else default_tracker())


def build_fallback(profiles: Sequence[ModelProfile], cooldowns: CooldownTracker | None = None) -> Model:
    if not profiles:
        raise ValueError("build_fallback needs at least one profile")
    tracker = cooldowns if cooldowns is not None else default_tracker()
    models = [build_model(p, tracker) for p in profiles]
    if len(models) == 1:
        return models[0]
    return FallbackModel(*models, fallback_on=(ModelAPIError, OutputTokenLimitExceeded))
