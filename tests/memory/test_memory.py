import pytest
from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from agent0.memory.base import Fact, RunSummary
from agent0.memory.extract import Extraction, build_extraction_agent, extract_and_apply
from agent0.memory.fusion import rrf, take_within_budget
from agent0.memory.inmemory import InMemoryMemoryStore


def test_rrf_prefers_items_ranked_high_in_both_lists():
    fused = dict(rrf([["a", "b", "c"], ["b", "d", "c"]]))
    ordered = sorted(fused, key=lambda k: -fused[k])
    assert ordered[0] == "b"
    assert set(ordered) == {"a", "b", "c", "d"}
    assert fused["b"] == pytest.approx(1 / 62 + 1 / 61)


def test_rrf_single_ranking_keeps_order():
    assert [k for k, _ in rrf([["x", "y", "z"]])] == ["x", "y", "z"]


def test_budget_caps_and_always_keeps_first_if_it_fits():
    items = ["a" * 40, "b" * 40, "c" * 40]
    assert take_within_budget(items, lambda s: s, 90) == items[:2]
    assert take_within_budget(items, lambda s: s, 10) == []


async def test_new_inserts_and_repeats_is_noop():
    store = InMemoryMemoryStore()
    f = Fact(content="brand never says cure")
    await store.apply(f, "new")
    await store.apply(Fact(content="brand never says cure"), "repeats", f.id)
    assert len(store.facts) == 1


async def test_changes_expires_target_and_links_new():
    store = InMemoryMemoryStore()
    old = Fact(content="deploy target is staging")
    await store.apply(old, "new")
    new = Fact(content="deploy target is production")
    await store.apply(new, "changes", old.id)
    assert store.facts[old.id].valid_to is not None
    assert store.facts[old.id].superseded_by == new.id
    assert [f.id for f in store.current_facts()] == [new.id]
    assert old.id in store.facts


async def test_ends_expires_without_replacement():
    store = InMemoryMemoryStore()
    old = Fact(content="user is on vacation")
    await store.apply(old, "new")
    await store.apply(Fact(content="user is back"), "ends", old.id)
    assert store.current_facts() == []
    assert store.facts[old.id].superseded_by is None
    assert len(store.facts) == 1


async def test_changes_without_target_raises():
    with pytest.raises(ValueError):
        await InMemoryMemoryStore().apply(Fact(content="x"), "changes")


async def test_recall_only_current_facts_scoped_and_capped():
    store = InMemoryMemoryStore(max_chars=60)
    old = Fact(content="report format is csv")
    await store.apply(old, "new")
    await store.apply(Fact(content="report format is parquet"), "changes", old.id)
    await store.apply(Fact(content="report owner is alice", scope="project", scope_id="p2"), "new")
    await store.save_run(RunSummary(run_id="r1", summary="built the report in parquet " * 5, outcome="ok"))
    recall = await store.recall("report format", scope="project", scope_id="p1")
    assert [f.content for f in recall.facts] == ["report format is parquet"]
    assert recall.past_runs == []  # budget exhausted by the fact
    wide = await InMemoryMemoryStore().recall("anything")
    assert wide.facts == [] and wide.render() == ""


def _fake_model(items: list[dict], seen: list[str]) -> FunctionModel:
    def respond(messages, info: AgentInfo) -> ModelResponse:
        seen.append(str(messages))
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, {"items": items})])

    return FunctionModel(respond)


async def test_extract_applies_verdicts_with_one_model_call():
    store = InMemoryMemoryStore()
    old = Fact(content="client prefers weekly reports sent on monday")
    gone = Fact(content="client uses the legacy dashboard")
    await store.apply(old, "new")
    await store.apply(gone, "new")
    seen: list[str] = []
    items = [
        {
            "content": "client prefers weekly reports sent on friday",
            "verdict": "changes",
            "target_id": old.id,
        },
        {"content": "client no longer uses the legacy dashboard", "verdict": "ends", "target_id": gone.id},
        {"content": "client's brand never says cure", "verdict": "new"},
        {"content": "ends with a bogus target", "verdict": "ends", "target_id": "nope"},
    ]
    agent = build_extraction_agent(_fake_model(items, seen))
    summary = (
        "The client prefers weekly reports sent on friday. The client uses the legacy dashboard no more."
    )
    applied = await extract_and_apply(store, summary, agent, run_id="run-9")

    assert len(seen) == 1
    assert old.id in seen[0] and gone.id in seen[0]
    assert [v for _, v, _ in applied] == ["changes", "ends", "new"]
    assert store.facts[old.id].valid_to is not None
    assert store.facts[gone.id].valid_to is not None
    current = {f.content for f in store.current_facts()}
    assert current == {"client prefers weekly reports sent on friday", "client's brand never says cure"}
    assert all(f.source_id == "run-9" for f, _, _ in applied)


async def test_extract_caps_at_five_items():
    store = InMemoryMemoryStore()
    items = [{"content": f"fact number {i}", "verdict": "new"} for i in range(5)]
    agent = build_extraction_agent(_fake_model(items, []))
    assert len(await extract_and_apply(store, "something happened today", agent)) == 5
    assert Extraction.model_json_schema()["properties"]["items"]["maxItems"] == 5
