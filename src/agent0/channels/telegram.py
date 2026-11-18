from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Awaitable, Callable, Iterable
from pathlib import Path
from typing import Any, NamedTuple

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ChatType, ParseMode
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    TelegramObject,
    User,
)

from agent0.channels.base import (
    ApprovalHandler,
    ApprovalRequest,
    InboundHandler,
    InboundTask,
    OutboundMessage,
)
from agent0.channels.formatting import html_text, split_message
from agent0.config import Settings, get_settings

StatusHandler = Callable[[], Awaitable[str]]
StopHandler = Callable[[str], Awaitable[str]]
Middleware = Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]]

CALLBACK_PREFIX = "ap"
CALLBACK_LIMIT_BYTES = 64
PHOTO_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".gif", ".webp"})
AUDIO_SUFFIXES = frozenset({".wav", ".mp3", ".ogg"})

HELP_TEXT = (
    "<b>agent0</b> runs tasks and reports back here.\n\n"
    "/task &lt;text&gt; - start a task (plain text in a private chat works too)\n"
    "/status - list recent runs\n"
    "/stop &lt;run id&gt; - stop a run\n"
    "/help - show this message"
)

log = logging.getLogger(__name__)


class ParsedCommand(NamedTuple):
    name: str
    args: str


def parse_command(text: str) -> ParsedCommand | None:
    if not text.startswith("/"):
        return None
    head, _, args = text.partition(" ")
    name = head[1:].split("@", 1)[0].lower()
    return ParsedCommand(name, args.strip())


def is_allowed(user_id: int, username: str | None, allowed: Iterable[str]) -> bool:
    for entry in allowed:
        ref = entry.strip().removeprefix("@")
        if not ref:
            continue
        if ref.isdigit():
            if ref == str(user_id):
                return True
        elif username and ref.lower() == username.lower():
            return True
    return False


def user_label(user: User) -> str:
    return f"@{user.username}" if user.username else user.full_name


def encode_approval_callback(approval_id: str, decision: str) -> str:
    if ":" in approval_id:
        raise ValueError("approval_id must not contain ':'")
    data = f"{CALLBACK_PREFIX}:{approval_id}:{decision}"
    if len(data.encode()) > CALLBACK_LIMIT_BYTES:
        raise ValueError(f"callback data exceeds {CALLBACK_LIMIT_BYTES} bytes")
    return data


def decode_approval_callback(data: str | None) -> tuple[str, str] | None:
    if not data:
        return None
    prefix, sep, rest = data.partition(":")
    approval_id, sep2, decision = rest.partition(":")
    if prefix != CALLBACK_PREFIX or not sep or not sep2 or not approval_id or not decision:
        return None
    return approval_id, decision


def attachment_kind(path: str) -> str:
    suffix = Path(path).suffix.lower()
    if suffix in PHOTO_SUFFIXES:
        return "photo"
    if suffix in AUDIO_SUFFIXES:
        return "audio"
    return "document"


class TelegramChannel:
    name = "telegram"

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        bot: Bot | None = None,
        status_handler: StatusHandler | None = None,
        stop_handler: StopHandler | None = None,
    ) -> None:
        if settings is None:
            settings = get_settings()
        if bot is None:
            if not settings.telegram_bot_token:
                raise ValueError("AGENT0_TELEGRAM_BOT_TOKEN is not set")
            bot = Bot(settings.telegram_bot_token)
        self._bot = bot
        self._allowed = list(settings.telegram_allowed_users)
        self._status_handler = status_handler
        self._stop_handler = stop_handler
        self._on_task: InboundHandler | None = None
        self._on_approval: ApprovalHandler | None = None
        self._dp = Dispatcher()
        self._dp.message.outer_middleware(self._guard)
        self._dp.callback_query.outer_middleware(self._guard)
        self._dp.message.register(self._handle_message, F.text)
        self._dp.callback_query.register(self._handle_callback, F.data.startswith(CALLBACK_PREFIX))

    async def start(self, on_task: InboundHandler, on_approval: ApprovalHandler) -> None:
        self._on_task = on_task
        self._on_approval = on_approval
        await self._dp.start_polling(self._bot, handle_signals=False)

    async def stop(self) -> None:
        try:
            await self._dp.stop_polling()
        except RuntimeError:
            # Not polling: nothing to stop.
            pass

    async def send(self, message: OutboundMessage) -> None:
        for chunk in split_message(message.text):
            await self._bot.send_message(message.chat_id, html_text(chunk), parse_mode=ParseMode.HTML)
        for path in message.attachments:
            await self._send_attachment(message.chat_id, path)

    async def request_approval(self, request: ApprovalRequest) -> None:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=option.capitalize(),
                        callback_data=encode_approval_callback(request.approval_id, option),
                    )
                    for option in request.options
                ]
            ]
        )
        text = f"<b>Approval needed</b> (run {html_text(request.run_id[:8])})\n{html_text(request.question)}"
        await self._bot.send_message(request.chat_id, text, parse_mode=ParseMode.HTML, reply_markup=keyboard)

    async def _guard(self, handler: Middleware, event: TelegramObject, data: dict[str, Any]) -> Any:
        user = getattr(event, "from_user", None)
        if user is not None and is_allowed(user.id, user.username, self._allowed):
            return await handler(event, data)
        # Showing the id lets the owner add themselves to AGENT0_TELEGRAM_ALLOWED_USERS on first contact.
        uid = user.id if user is not None else "unknown"
        log.info("telegram: refused user id=%s", uid)
        refusal = f"Sorry, this bot is private. Your Telegram user id is {uid}; ask the owner to allow it."
        if isinstance(event, CallbackQuery):
            await self._bot.answer_callback_query(event.id, text=refusal, show_alert=True)
        elif isinstance(event, Message):
            await self._bot.send_message(event.chat.id, refusal)
        return None

    async def _handle_message(self, message: Message) -> None:
        chat_id = str(message.chat.id)
        if message.from_user is None:
            return
        text = message.text or ""
        parsed = parse_command(text)
        if parsed is None:
            if message.chat.type == ChatType.PRIVATE:
                await self._start_task(chat_id, str(message.from_user.id), text.strip())
            return
        match parsed.name:
            case "task":
                await self._start_task(chat_id, str(message.from_user.id), parsed.args)
            case "status":
                await self._reply(chat_id, await self._status_text())
            case "stop":
                await self._reply(chat_id, await self._stop_text(parsed.args))
            case "start" | "help":
                await self._reply(chat_id, HELP_TEXT)
            case _:
                await self._reply(chat_id, f"Unknown command /{html_text(parsed.name)}.\n\n{HELP_TEXT}")

    async def _start_task(self, chat_id: str, user: str, text: str) -> None:
        if not text:
            await self._reply(chat_id, "Usage: /task &lt;what you want done&gt;")
            return
        if self._on_task is None:
            await self._reply(chat_id, "Not ready yet, try again in a moment.")
            return
        try:
            run_id = await self._on_task(InboundTask(chat_id=chat_id, user=user, text=text))
        except Exception as exc:
            await self._reply(chat_id, f"Could not start the task: {html_text(type(exc).__name__)}")
            return
        await self._reply(chat_id, f"Started run <code>{html_text(run_id)}</code>")

    async def _status_text(self) -> str:
        if self._status_handler is None:
            return "Status is not available."
        return html_text(await self._status_handler())

    async def _stop_text(self, run_id: str) -> str:
        if not run_id:
            return "Usage: /stop &lt;run id&gt;"
        if self._stop_handler is None:
            return "Stopping runs is not available."
        return html_text(await self._stop_handler(run_id))

    async def _handle_callback(self, callback: CallbackQuery) -> None:
        decoded = decode_approval_callback(callback.data)
        if decoded is None or self._on_approval is None:
            await self._bot.answer_callback_query(callback.id, text="This action is no longer valid.")
            return
        approval_id, decision = decoded
        who = user_label(callback.from_user)
        await self._on_approval(approval_id, decision, str(callback.from_user.id))
        await self._bot.answer_callback_query(callback.id, text=f"Recorded: {decision}")
        if isinstance(callback.message, Message):
            original = html_text(callback.message.text or "")
            text = f"{original}\n\n<b>{html_text(decision)}</b> by {html_text(who)}"
            await self._bot.edit_message_text(
                text,
                chat_id=callback.message.chat.id,
                message_id=callback.message.message_id,
                parse_mode=ParseMode.HTML,
                reply_markup=None,
            )

    async def _reply(self, chat_id: str, html: str) -> None:
        await self._bot.send_message(chat_id, html, parse_mode=ParseMode.HTML)

    async def _send_attachment(self, chat_id: str, path: str) -> None:
        if not await asyncio.to_thread(os.path.isfile, path):
            await self._reply(chat_id, f"Missing attachment: {html_text(os.path.basename(path))}")
            return
        kind = attachment_kind(path)
        file = FSInputFile(path)
        if kind == "photo":
            await self._bot.send_photo(chat_id, file)
        elif kind == "audio":
            await self._bot.send_audio(chat_id, file)
        else:
            await self._bot.send_document(chat_id, file)
