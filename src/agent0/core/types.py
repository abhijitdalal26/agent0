from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def new_id() -> str:
    return uuid4().hex


def utcnow() -> datetime:
    return datetime.now(UTC)


class RunStatus(StrEnum):
    PENDING = "pending"
    PLANNING = "planning"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    WAITING_APPROVAL = "waiting_approval"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    STOPPED = "stopped"


class Capability(StrEnum):
    CHAT = "chat"
    VISION = "vision"
    IMAGE_GEN = "image_gen"
    TTS = "tts"
    STT = "stt"
    EMBEDDING = "embedding"


class EventType(StrEnum):
    RUN_STARTED = "run.started"
    PLAN_CREATED = "plan.created"
    MODEL_CALL = "model.call"
    TOOL_CALL = "tool.call"
    TOOL_RESULT = "tool.result"
    SKILL_LOADED = "skill.loaded"
    MEMORY_RECALLED = "memory.recalled"
    MEMORY_SAVED = "memory.saved"
    KNOWLEDGE_READ = "knowledge.read"
    CHECK_RESULT = "check.result"
    APPROVAL_REQUESTED = "approval.requested"
    APPROVAL_DECIDED = "approval.decided"
    BUDGET_EXCEEDED = "budget.exceeded"
    ERROR = "error"
    RUN_FINISHED = "run.finished"


class Event(BaseModel):
    id: str = Field(default_factory=new_id)
    run_id: str
    seq: int = 0
    type: EventType
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utcnow)
    prev_hash: str | None = None
    hash: str | None = None


class Budget(BaseModel):
    max_usd: float = 1.0
    max_steps: int = 40
    max_minutes: int = 30
    max_retries: int = 2


class NotifyLevel(StrEnum):
    FINAL_ONLY = "final_only"
    MILESTONES = "milestones"
    EVERYTHING = "everything"


class Task(BaseModel):
    id: str = Field(default_factory=new_id)
    title: str
    prompt: str
    source: str = "cli"
    agent: str = "executor"
    status: RunStatus = RunStatus.PENDING
    notify_level: NotifyLevel = NotifyLevel.MILESTONES
    budget: Budget = Field(default_factory=Budget)
    chat_id: str | None = None
    criteria: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utcnow)


class Run(BaseModel):
    id: str = Field(default_factory=new_id)
    task_id: str
    attempt: int = 1
    status: RunStatus = RunStatus.PENDING
    agent: str = "executor"
    model_profile: str | None = None
    current_step: str | None = None
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    started_at: datetime = Field(default_factory=utcnow)
    ended_at: datetime | None = None


class Artifact(BaseModel):
    id: str = Field(default_factory=new_id)
    run_id: str
    path: str
    kind: str = "other"
    size: int = 0
    url: str | None = None
