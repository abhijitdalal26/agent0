from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from aiogram import Bot
from aiogram.types import CallbackQuery, Chat, FSInputFile, InlineKeyboardMarkup, Message, User

from agent0.channels.base import ApprovalRequest, InboundTask, OutboundMessage
from agent0.channels.telegram import (
    HELP_TEXT,
    TelegramChannel,
    attachment_kind,
    decode_approval_callback,
    encode_approval_callback,
    is_allowed,
    parse_command,
)
from agent0.config import Settings

OWNER = User(id=111, is_bot=False, first_name="Owner", username="alice")
STRANGER = User(id=222, is_bot=False, first_name="Eve", username="eve")


def _settings() -> Settings:
    return Settings(_env_file=None, telegram_bot_token="123:abc", telegram_allowed_users=["111", "@Alice"])


def _message(text: str, user: User = OWNER, chat_type: str = "private") -> Message:
    return Message(
        message_id=1,
        date=datetime.now(UTC),
        chat=Chat(id=500, type=chat_type),
        from_user=user,
        text=text,
    )


@pytest.fixture
def bot() -> AsyncMock:
    return AsyncMock(spec=Bot)


@pytest.fixture
def channel(bot: AsyncMock) -> TelegramChannel:
    return TelegramChannel(_settings(), bot=bot)


def test_parse_command_extracts_name_and_args():
    assert parse_command("/task write a poem") == ("task", "write a poem")
    assert parse_command("/task@MyBot  do x ") == ("task", "do x")
    assert parse_command("/STATUS") == ("status", "")
    assert parse_command("hello /task") is None


def test_is_allowed_matches_id_and_username():
    assert is_allowed(111, None, ["111"])
    assert is_allowed(999, "Alice", ["@alice"])
    assert not is_allowed(999, "bob", ["alice"])
    assert not is_allowed(999, None, ["@alice"])
    assert not is_allowed(111, "x", [])
    assert not is_allowed(1, None, ["  "])


def test_callback_round_trip():
    data = encode_approval_callback("3f2c9a", "approve")
    assert decode_approval_callback(data) == ("3f2c9a", "approve")


def test_callback_rejects_over_64_bytes():
    with pytest.raises(ValueError):
        encode_approval_callback("x" * 60, "approve")


def test_callback_rejects_colon_in_id():
    with pytest.raises(ValueError):
        encode_approval_callback("a:b", "approve")


@pytest.mark.parametrize("data", [None, "", "zz:1:approve", "ap:only", "ap::approve", "ap:id:"])
def test_callback_decode_rejects_malformed(data):
    assert decode_approval_callback(data) is None


@pytest.mark.parametrize(
    ("path", "kind"),
    [("a.PNG", "photo"), ("b.wav", "audio"), ("c.mp3", "audio"), ("d.ogg", "audio"), ("e.pdf", "document")],
)
def test_attachment_kind(path, kind):
    assert attachment_kind(path) == kind


async def test_task_command_starts_run_and_replies_with_id(channel, bot):
    channel._on_task = AsyncMock(return_value="run42")
    await channel._handle_message(_message("/task make a logo"))
    task = channel._on_task.await_args.args[0]
    assert task == InboundTask(chat_id="500", user="111", text="make a logo")
    sent = bot.send_message.await_args
    assert "run42" in sent.args[1]
    assert sent.kwargs["parse_mode"] == "HTML"


async def test_task_without_text_shows_usage(channel, bot):
    channel._on_task = AsyncMock()
    await channel._handle_message(_message("/task"))
    channel._on_task.assert_not_awaited()
    assert "Usage" in bot.send_message.await_args.args[1]


async def test_plain_text_in_private_chat_is_a_task(channel):
    channel._on_task = AsyncMock(return_value="r1")
    await channel._handle_message(_message("summarise the report"))
    assert channel._on_task.await_args.args[0].text == "summarise the report"


async def test_plain_text_in_group_is_ignored(channel, bot):
    channel._on_task = AsyncMock(return_value="r1")
    await channel._handle_message(_message("hello all", chat_type="group"))
    channel._on_task.assert_not_awaited()
    bot.send_message.assert_not_awaited()


async def test_task_handler_failure_is_reported(channel, bot):
    channel._on_task = AsyncMock(side_effect=RuntimeError("boom"))
    await channel._handle_message(_message("/task x"))
    assert "RuntimeError" in bot.send_message.await_args.args[1]


async def test_status_and_stop_use_constructor_handlers(bot):
    status = AsyncMock(return_value="2 running")
    stop = AsyncMock(return_value="stopped <r1>")
    channel = TelegramChannel(_settings(), bot=bot, status_handler=status, stop_handler=stop)
    await channel._handle_message(_message("/status"))
    assert bot.send_message.await_args.args[1] == "2 running"
    await channel._handle_message(_message("/stop r1"))
    stop.assert_awaited_once_with("r1")
    assert bot.send_message.await_args.args[1] == "stopped &lt;r1&gt;"


async def test_stop_without_id_shows_usage(channel, bot):
    await channel._handle_message(_message("/stop"))
    assert "Usage" in bot.send_message.await_args.args[1]


async def test_status_without_handler_says_unavailable(channel, bot):
    await channel._handle_message(_message("/status"))
    assert "not available" in bot.send_message.await_args.args[1]


@pytest.mark.parametrize("text", ["/start", "/help"])
async def test_start_and_help_explain_the_bot(channel, bot, text):
    await channel._handle_message(_message(text))
    assert bot.send_message.await_args.args[1] == HELP_TEXT


async def test_unknown_command_shows_help(channel, bot):
    await channel._handle_message(_message("/nope"))
    assert "Unknown command /nope" in bot.send_message.await_args.args[1]


async def test_guard_refuses_unknown_user_and_runs_nothing(channel, bot):
    handler = AsyncMock()
    await channel._guard(handler, _message("/task x", user=STRANGER), {"event_from_user": STRANGER})
    handler.assert_not_awaited()
    assert "private" in bot.send_message.await_args.args[1]
    assert str(STRANGER.id) in bot.send_message.await_args.args[1]


async def test_guard_passes_allowed_user_by_username(channel):
    handler = AsyncMock(return_value="ok")
    message = _message("/status", user=User(id=999, is_bot=False, first_name="A", username="alice"))
    assert await channel._guard(handler, message, {}) == "ok"
    handler.assert_awaited_once()


async def test_guard_refuses_callback_with_alert(channel, bot):
    handler = AsyncMock()
    callback = CallbackQuery(id="cb1", from_user=STRANGER, chat_instance="ci", data="ap:x:approve")
    await channel._guard(handler, callback, {})
    handler.assert_not_awaited()
    assert bot.answer_callback_query.await_args.kwargs["show_alert"] is True


async def test_send_splits_long_text_and_escapes(channel, bot):
    await channel.send(OutboundMessage(chat_id="500", text="<x> & " + "a" * 9000))
    texts = [c.args[1] for c in bot.send_message.await_args_list]
    assert len(texts) == 3
    assert all(len(t) <= 4096 for t in texts)
    assert texts[0].startswith("&lt;x&gt; &amp; ")


async def test_send_routes_attachments_by_kind(channel, bot, tmp_path):
    files = {}
    for name in ["pic.png", "clip.wav", "doc.pdf"]:
        path = tmp_path / name
        path.write_bytes(b"x")
        files[name] = str(path)
    await channel.send(
        OutboundMessage(
            chat_id="500", text="", attachments=[files["pic.png"], files["clip.wav"], files["doc.pdf"]]
        )
    )
    assert isinstance(bot.send_photo.await_args.args[1], FSInputFile)
    assert isinstance(bot.send_audio.await_args.args[1], FSInputFile)
    assert isinstance(bot.send_document.await_args.args[1], FSInputFile)
    bot.send_message.assert_not_awaited()


async def test_send_reports_missing_attachment(channel, bot, tmp_path):
    await channel.send(OutboundMessage(chat_id="500", text="", attachments=[str(tmp_path / "gone.pdf")]))
    bot.send_document.assert_not_awaited()
    assert "Missing attachment: gone.pdf" in bot.send_message.await_args.args[1]


async def test_request_approval_builds_buttons_that_fit_the_limit(channel, bot):
    await channel.request_approval(
        ApprovalRequest(approval_id="ap-1", run_id="run9", chat_id="500", question="Ship it?")
    )
    kwargs = bot.send_message.await_args.kwargs
    markup = kwargs["reply_markup"]
    assert isinstance(markup, InlineKeyboardMarkup)
    buttons = markup.inline_keyboard[0]
    assert [b.text for b in buttons] == ["Approve", "Reject"]
    for button in buttons:
        assert decode_approval_callback(button.callback_data)[0] == "ap-1"
        assert len(button.callback_data.encode()) <= 64


async def test_approval_press_records_decision_and_edits_message(channel, bot):
    channel._on_approval = AsyncMock()
    prompt = _message("Ship <it>?")
    callback = CallbackQuery(
        id="cb1",
        from_user=OWNER,
        chat_instance="ci",
        data=encode_approval_callback("ap-1", "reject"),
        message=prompt,
    )
    await channel._handle_callback(callback)
    channel._on_approval.assert_awaited_once_with("ap-1", "reject", "111")
    bot.answer_callback_query.assert_awaited_once()
    edit = bot.edit_message_text.await_args
    assert edit.args[0] == "Ship &lt;it&gt;?\n\n<b>reject</b> by @alice"
    assert edit.kwargs["reply_markup"] is None


async def test_invalid_callback_is_answered_without_deciding(channel, bot):
    channel._on_approval = AsyncMock()
    callback = CallbackQuery(id="cb1", from_user=OWNER, chat_instance="ci", data="ap:broken")
    await channel._handle_callback(callback)
    channel._on_approval.assert_not_awaited()
    assert "no longer valid" in bot.answer_callback_query.await_args.kwargs["text"]


async def test_stop_before_start_is_a_no_op(channel):
    await channel.stop()
