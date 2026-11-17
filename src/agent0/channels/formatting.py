from __future__ import annotations

from collections.abc import Iterator
from html import escape

from pydantic import BaseModel, Field

from agent0.core.types import Event, EventType, RunStatus

TELEGRAM_TEXT_LIMIT = 4096
_MILESTONE_DETAIL_CHARS = 200


class CheckLine(BaseModel):
    check_id: str
    status: str
    evidence: str = ""


class RunReport(BaseModel):
    run_id: str
    status: RunStatus
    cost_usd: float = 0.0
    url: str | None = None
    verdicts: list[CheckLine] = Field(default_factory=list)


def html_text(text: str) -> str:
    return escape(text, quote=False)


def _units(text: str) -> int:
    # Telegram's 4096 limit counts UTF-16 code units, not code points.
    return len(text.encode("utf-16-le")) // 2


def _clip(text: str, limit: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _pieces(text: str, limit: int) -> Iterator[str]:
    for line in text.splitlines(keepends=True):
        if _units(html_text(line)) <= limit:
            yield line
            continue
        piece, size = "", 0
        for char in line:
            cost = _units(html_text(char))
            if size + cost > limit:
                yield piece
                piece, size = "", 0
            piece += char
            size += cost
        if piece:
            yield piece


def split_message(text: str, limit: int = TELEGRAM_TEXT_LIMIT) -> list[str]:
    """Split raw text into chunks whose HTML-escaped form fits one Telegram message."""
    chunks: list[str] = []
    buf, size = "", 0
    for piece in _pieces(text, limit):
        cost = _units(html_text(piece))
        if buf and size + cost > limit:
            chunks.append(buf)
            buf, size = "", 0
        buf += piece
        size += cost
    if buf:
        chunks.append(buf)
    return chunks


def render_verdict_table(verdicts: list[CheckLine]) -> str:
    rows = [(v.check_id, v.status.upper(), _clip(v.evidence, 40)) for v in verdicts]
    names = [_clip(name, 24) for name, _, _ in rows]
    name_w = max([len("CHECK"), *map(len, names)])
    status_w = max([len("STATUS"), *(len(status) for _, status, _ in rows)])
    header = f"{'CHECK':<{name_w}}  {'STATUS':<{status_w}}  EVIDENCE"
    body = [
        f"{name:<{name_w}}  {status:<{status_w}}  {evidence}"
        for name, (_, status, evidence) in zip(names, rows, strict=True)
    ]
    return "\n".join([header, *body])


def render_report(report: RunReport) -> str:
    lines = [
        f"<b>Run {html_text(report.run_id)}: {report.status.upper()}</b>",
        f"Cost: ${report.cost_usd:.4f}",
    ]
    if report.verdicts:
        lines.append(f"<pre>{html_text(render_verdict_table(report.verdicts))}</pre>")
    if report.url:
        lines.append(f'<a href="{escape(report.url)}">Open run</a>')
    return "\n".join(lines)


def render_milestone(event: Event) -> str | None:
    payload = event.payload
    if event.type is EventType.PLAN_CREATED:
        detail = "plan ready"
    elif event.type is EventType.CHECK_RESULT:
        detail = f"check {payload.get('check_id', '?')}: {payload.get('status', '?')}"
    elif event.type is EventType.APPROVAL_REQUESTED:
        detail = "waiting for your approval"
    elif event.type is EventType.BUDGET_EXCEEDED:
        detail = "budget exceeded"
    elif event.type is EventType.ERROR:
        detail = f"error: {payload.get('message', 'unknown')}"
    elif event.type is EventType.RUN_FINISHED:
        detail = f"finished: {payload.get('status', '?')}"
    else:
        return None
    return f"<b>{html_text(event.run_id[:8])}</b> {html_text(_clip(detail, _MILESTONE_DETAIL_CHARS))}"
