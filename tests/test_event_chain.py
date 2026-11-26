from agent0.core.events import MemoryEventSink, verify_chain
from agent0.core.types import EventType


async def test_memory_sink_chains_events():
    sink = MemoryEventSink()
    a = await sink.emit("r1", EventType.RUN_STARTED, {"task_id": "t1"})
    b = await sink.emit("r1", EventType.TOOL_CALL, {"tool": "shell"})
    c = await sink.emit("r2", EventType.RUN_STARTED)

    assert a.prev_hash is None and a.hash
    assert b.prev_hash == a.hash and b.hash != a.hash
    # Chains are per run: r2 restarts at genesis.
    assert c.prev_hash is None
    assert verify_chain(sink.events[:2]) == (True, None)


async def test_verify_chain_detects_tampering():
    sink = MemoryEventSink()
    await sink.emit("r1", EventType.RUN_STARTED)
    await sink.emit("r1", EventType.TOOL_CALL, {"tool": "shell", "args": {"command": "ls"}})
    events = sink.events

    ok, bad = verify_chain(events)
    assert ok and bad is None

    # Alter a payload after the fact: the digest no longer matches.
    forged = {"tool": "shell", "args": {"command": "rm -rf /"}}
    tampered = [events[0], events[1].model_copy(update={"payload": forged})]
    ok, bad = verify_chain(tampered)
    assert not ok and bad == 2

    # A missing hash (legacy row) also breaks verification.
    unchained = [events[0], events[1].model_copy(update={"hash": None})]
    ok, bad = verify_chain(unchained)
    assert not ok and bad == 2


def test_verify_chain_empty():
    assert verify_chain([]) == (True, None)
