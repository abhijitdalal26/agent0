from __future__ import annotations

import json

from api_fakes import FakeStream

from agent0.core.types import Event, EventType, RunStatus

BASE = "/api/v1"


def _read(client, path, headers=None):
    events = []
    with client.stream("GET", BASE + path, headers=headers or {}) as r:
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        cur: dict[str, str] = {}
        for line in r.iter_lines():
            if line == "":
                if cur:
                    events.append(cur)
                cur = {}
            elif not line.startswith(":"):
                k, _, v = line.partition(": ")
                cur[k] = v
    return events


async def test_replay_from_last_event_id_then_live(env):
    run = await env.repos.seed_run()
    env.repos.add_events(run.id, 4)
    live = [
        Event(run_id=run.id, seq=4, type=EventType.TOOL_CALL),
        Event(run_id=run.id, seq=5, type=EventType.ERROR, payload={"m": "x"}),
        Event(run_id="other", seq=9, type=EventType.ERROR),
    ]
    env.stream.live = live
    # the live generator ends, which ends the response
    frames = _read(env.client, f"/runs/{run.id}/stream", {"Last-Event-ID": "2"})
    assert [f["id"] for f in frames] == ["3", "4", "5"]
    assert frames[0]["event"] == "tool.call" and frames[2]["event"] == "error"
    data = json.loads(frames[2]["data"])
    assert data["seq"] == 5 and data["run_id"] == run.id and data["payload"] == {"m": "x"}


async def test_replay_without_header_starts_at_beginning(env):
    run = await env.repos.seed_run(RunStatus.SUCCEEDED)
    env.repos.add_events(run.id, 3)
    frames = _read(env.client, f"/runs/{run.id}/stream")
    assert [f["id"] for f in frames] == ["1", "2", "3"]


async def test_finished_run_stream_ends_after_replay(env):
    run = await env.repos.seed_run(RunStatus.FAILED)
    env.repos.add_events(run.id, 2)
    env.stream = FakeStream([Event(run_id=run.id, seq=3, type=EventType.RUN_FINISHED)])
    env.deps.event_stream = env.stream
    assert [f["id"] for f in _read(env.client, f"/runs/{run.id}/stream", {"Last-Event-ID": "1"})] == ["2"]


async def test_global_stream_and_404(env):
    env.stream.live = [
        Event(run_id="a", seq=1, type=EventType.RUN_STARTED),
        Event(run_id="b", seq=1, type=EventType.RUN_FINISHED),
    ]
    frames = _read(env.client, "/stream")
    assert [f["event"] for f in frames] == ["run.started", "run.finished"]
    assert env.client.get(f"{BASE}/runs/nope/stream").status_code == 404
