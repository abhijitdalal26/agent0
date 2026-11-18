import pytest
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from agent0.config import Settings
from agent0.core.events import MemoryEventSink
from agent0.core.types import Budget, EventType, RunStatus, Task
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


async def test_task_budget_reaches_budget_meter(runtime, monkeypatch):
    seen = []
    real = steps_mod.BudgetMeter

    def spy(**kwargs):
        seen.append(kwargs)
        return real(**kwargs)

    monkeypatch.setattr(steps_mod, "BudgetMeter", spy)
    task = Task(
        title="hello",
        prompt="Write hello.txt",
        budget=Budget(max_usd=0.5, max_minutes=12),
    )
    _, outcome = await LocalOrchestrator(runtime).run_to_end(task)
    assert outcome.status == RunStatus.SUCCEEDED, outcome
    # executor agent.md sets max_steps: 40, which overrides the task value by design
    assert seen and seen[0]["max_usd"] == 0.5 and seen[0]["max_minutes"] == 12


async def test_required_criteria_are_kept_and_enforced(runtime):
    required = {
        "id": "must",
        "type": "artifact",
        "description": "hello.txt mentions planets",
        "config": {"path": "hello.txt", "required_patterns": ["planets"]},
    }
    task = Task(title="hello", prompt="Write hello.txt", criteria=[required], budget=Budget(max_retries=0))
    _, outcome = await LocalOrchestrator(runtime).run_to_end(task)
    assert outcome.status == RunStatus.FAILED
    assert {v.check_id for v in outcome.report.verdicts} >= {"must", "c1"}


async def test_crash_outside_drive_marks_run_failed(runtime, monkeypatch):
    import agent0.orchestrator.local as local

    async def boom(task, steps):
        raise RuntimeError("planner exploded")

    monkeypatch.setattr(local, "drive", boom)
    statuses = []

    async def spy(task, run_id, status, step=None):
        statuses.append(status)

    orch = LocalOrchestrator(runtime)
    monkeypatch.setattr(orch.engine, "set_status", spy)
    _, outcome = await orch.run_to_end(Task(title="t", prompt="p"))
    assert outcome.status == RunStatus.FAILED and statuses == [RunStatus.FAILED]
    await orch.stop(next(iter(orch.running)))
    assert statuses[-1] == RunStatus.STOPPED


async def test_hallucinated_tool_is_corrected_not_fatal(tmp_path, monkeypatch):
    seen: dict[str, int] = {}

    def flaky(messages, info: AgentInfo) -> ModelResponse:
        phase = "plan" if info.output_tools else "exec"
        seen[phase] = seen.get(phase, 0) + 1
        if seen[phase] <= 2:
            return ModelResponse(parts=[ToolCallPart("json", {"goal": "x"})])
        return brain(messages, info)

    monkeypatch.setenv("GROQ_API_KEY", "test")
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    monkeypatch.setattr(steps_mod, "build_fallback", lambda profiles: FunctionModel(flaky))
    monkeypatch.setattr(steps_mod, "build_model", lambda profile: FunctionModel(brain))
    settings = Settings(sandbox="local", workspace_root=tmp_path / "ws", skills_dirs=[], plugins_dirs=[])
    rt = build_runtime(settings, events=MemoryEventSink())
    _, outcome = await LocalOrchestrator(rt).run_to_end(Task(title="hello", prompt="Write hello.txt"))
    assert outcome.status == RunStatus.SUCCEEDED, outcome
    assert set(seen) == {"plan", "exec"}
