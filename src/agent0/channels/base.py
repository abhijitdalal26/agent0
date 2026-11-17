from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Protocol

from pydantic import BaseModel, Field


class OutboundMessage(BaseModel):
    chat_id: str
    text: str
    attachments: list[str] = Field(default_factory=list)


class ApprovalRequest(BaseModel):
    approval_id: str
    run_id: str
    chat_id: str
    question: str
    options: list[str] = Field(default_factory=lambda: ["approve", "reject"])


class InboundTask(BaseModel):
    chat_id: str
    user: str
    text: str


InboundHandler = Callable[[InboundTask], Awaitable[str]]
ApprovalHandler = Callable[[str, str, str], Awaitable[None]]


class Channel(Protocol):
    name: str

    async def send(self, message: OutboundMessage) -> None: ...
    async def request_approval(self, request: ApprovalRequest) -> None: ...
    async def start(self, on_task: InboundHandler, on_approval: ApprovalHandler) -> None: ...
    async def stop(self) -> None: ...
