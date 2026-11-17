import pytest
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from agent0.config import Settings
from agent0.core.events import MemoryEventSink
from agent0.core.types import EventType, RunStatus, Task
from agent0.orchestrator import steps as steps_mod
from agent0.orchestrator.local import LocalOrchestrator
from agent0.orchestrator.runtime import build_runtime

SPEC = {
    "goal": "write hello.txt",
    "steps": ["write the file"],
    "criteria": [
        {
            "id": "c1",
            "type": "artifact",
            "description": "hello.txt says hello",
            "config": {"path": "hello.txt", "required_patterns": ["hello"]},
        }
    ],
}


def brain(messages, info: AgentInfo) -> ModelResponse:
    if info.output_tools:
        props = info.output_tools[0].parameters_json_schema.get("properties", {})
        args = SPEC if "goal" in props else {"items": []}
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, args)])
    returned = any(isinstance(p, ToolReturnPart) for m in messages for p in getattr(m, "parts", []))
    if not returned:
        return ModelResponse(
            parts=[ToolCallPart("write_file", {"path": "hello.txt", "content": "hello world"})]
        )
    return ModelResponse(parts=[TextPart("Wrote hello.txt")])


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test")
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    monkeypatch.setattr(steps_mod, "build_fallback", lambda profiles: FunctionModel(brain))
    monkeypatch.setattr(steps_mod, "build_model", lambda profile: FunctionModel(brain))
    settings = Settings(sandbox="local", workspace_root=tmp_path / "ws", skills_dirs=[], plugins_dirs=[])
    return build_runtime(settings, events=MemoryEventSink())


async def test_task_runs_end_to_end(runtime):
    orch = LocalOrchestrator(runtime)
    run_id, outcome = await orch.run_to_end(Task(title="hello", prompt="Write hello.txt containing hello"))
    assert outcome.status == RunStatus.SUCCEEDED, outcome
    assert (runtime.settings.workspace_root / run_id / "hello.txt").read_text() == "hello world"
    types = [e.type for e in runtime.events.events]
    for expected in (
        EventType.PLAN_CREATED,
        EventType.TOOL_CALL,
        EventType.CHECK_RESULT,
        EventType.RUN_FINISHED,
    ):
        assert expected in types
    assert runtime.usage.records
