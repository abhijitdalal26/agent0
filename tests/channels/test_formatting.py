from datetime import UTC, datetime

from agent0.channels.formatting import (
    CheckLine,
    RunReport,
    _units,
    html_text,
    render_milestone,
    render_report,
    render_verdict_table,
    split_message,
)
from agent0.core.types import Event, EventType, RunStatus


def _verdict(check_id: str, status: str, evidence: str = "") -> CheckLine:
    return CheckLine(check_id=check_id, status=status, evidence=evidence)


def test_html_text_escapes_markup_only():
    assert html_text('<b>"x" & y</b>') == '&lt;b&gt;"x" &amp; y&lt;/b&gt;'


def test_split_short_text_is_one_chunk():
    assert split_message("hello") == ["hello"]


def test_split_keeps_every_chunk_under_limit_and_loses_nothing():
    text = "line of text\n" * 1000
    chunks = split_message(text)
    assert len(chunks) > 1
    assert all(_units(html_text(c)) <= 4096 for c in chunks)
    assert "".join(chunks) == text


def test_split_counts_escaped_length():
    text = "&" * 3000
    chunks = split_message(text)
    assert all(_units(html_text(c)) <= 4096 for c in chunks)
    assert "".join(chunks) == text


def test_split_counts_utf16_units_for_emoji():
    text = "\U0001f600" * 3000
    chunks = split_message(text)
    assert all(_units(c) <= 4096 for c in chunks)
    assert "".join(chunks) == text


def test_verdict_table_aligns_columns():
    table = render_verdict_table(
        [
            _verdict("build", "pass", "exit 0"),
            _verdict("tests_with_long_name", "fail", "2 failed"),
        ]
    )
    lines = table.splitlines()
    assert lines[0].startswith("CHECK")
    assert lines[1].index("PASS") == lines[0].index("STATUS") == lines[2].index("FAIL")


def test_render_report_contains_status_cost_table_and_escaped_link():
    report = RunReport(
        run_id="abc123",
        status=RunStatus.SUCCEEDED,
        cost_usd=0.12345,
        url="https://example.com/runs?a=1&b=2",
        verdicts=[_verdict("build", "pass", "<ok>")],
    )
    html = render_report(report)
    assert "<b>Run abc123: SUCCEEDED</b>" in html
    assert "Cost: $0.1235" in html
    assert "<pre>" in html and "&lt;ok&gt;" in html
    assert 'href="https://example.com/runs?a=1&amp;b=2"' in html


def test_render_report_without_verdicts_or_url():
    html = render_report(RunReport(run_id="r1", status=RunStatus.FAILED))
    assert "<pre>" not in html and "href" not in html


def test_milestone_for_check_result():
    event = Event(
        run_id="0123456789ab",
        type=EventType.CHECK_RESULT,
        payload={"check_id": "build", "status": "pass"},
        created_at=datetime.now(UTC),
    )
    assert render_milestone(event) == "<b>01234567</b> check build: pass"


def test_milestone_skips_noisy_events():
    event = Event(run_id="r1", type=EventType.TOOL_CALL)
    assert render_milestone(event) is None


def test_milestone_clips_long_error_detail():
    event = Event(run_id="r1", type=EventType.ERROR, payload={"message": "x" * 500})
    line = render_milestone(event)
    assert line is not None and len(line) < 260
