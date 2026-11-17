from agent0.core.events import MemoryEventSink
from agent0.core.types import EventType


async def test_event_sink_sequences_per_run():
    sink = MemoryEventSink()
    a = await sink.emit("r1", EventType.RUN_STARTED)
    b = await sink.emit("r1", EventType.TOOL_CALL, {"tool": "shell"})
    c = await sink.emit("r2", EventType.RUN_STARTED)
    assert (a.seq, b.seq, c.seq) == (1, 2, 1)
