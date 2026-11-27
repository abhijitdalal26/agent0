import io
from types import SimpleNamespace

from PIL import Image
from pydantic_ai import Agent
from pydantic_ai.messages import ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from agent0.orchestrator.tools import fit_image, knowledge_toolset, query_sql, search_knowledge


def _png(w: int, h: int, fmt: str = "PNG") -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), "teal").save(buf, format=fmt)
    return buf.getvalue()


def test_fit_image_makes_exact_size_and_format():
    out = Image.open(io.BytesIO(fit_image(_png(1024, 1024, "JPEG"), "1080x1080", "hero.png")))
    assert (out.size, out.format) == ((1080, 1080), "PNG")
    wide = Image.open(io.BytesIO(fit_image(_png(1536, 1024), "1080x1080", "a.png")))
    assert wide.size == (1080, 1080)


def test_fit_image_leaves_matching_or_undecodable_data():
    data = _png(64, 64)
    assert fit_image(data, "64x64", "x.png") == data
    assert fit_image(b"not an image", "64x64", "x.png") == b"not an image"
    assert fit_image(data, "16:9", "x.png") == data


async def test_tool_errors_are_returned_not_raised():
    docs = SimpleNamespace(kind="docs")
    ctx = SimpleNamespace(deps=SimpleNamespace(knowledge={"northwind": docs}))
    assert await query_sql(ctx, "northwind", "select 1") == "error: northwind is not a SQL source"  # type: ignore[arg-type]
    assert (await query_sql(ctx, "nope", "select 1")).startswith("error: unknown source")  # type: ignore[arg-type]


async def test_keyerror_is_returned_not_raised():
    class Boom:
        kind = "docs"

        async def search(self, query, limit=5):
            raise KeyError("quality")

    ctx = SimpleNamespace(deps=SimpleNamespace(knowledge={"sales": Boom()}))
    out = await search_knowledge(ctx, "sales", "q")  # type: ignore[arg-type]
    assert out == "error: 'quality'"


async def test_sql_errors_reach_the_model_as_text():
    import psycopg

    from agent0.knowledge.sql import SqlKnowledgeSource

    async def boom(sql, params):
        raise psycopg.errors.UndefinedTable('relation "sqlite_master" does not exist')

    src = SqlKnowledgeSource("sales", executor=boom)
    ctx = SimpleNamespace(deps=SimpleNamespace(knowledge={"sales": src}))
    out = await query_sql(ctx, "sales", "select name from sqlite_master")  # type: ignore[arg-type]
    assert out.startswith("error:") and "sqlite_master" in out


async def test_wrapped_tools_keep_their_schema():
    seen: dict[str, object] = {}

    def model(_messages, info: AgentInfo) -> ModelResponse:
        seen.update({t.name: t for t in info.function_tools})
        return ModelResponse(parts=[TextPart("done")])

    await Agent(FunctionModel(model), toolsets=[knowledge_toolset()]).run("hi")
    tool = seen["search_knowledge"]
    assert set(tool.parameters_json_schema["properties"]) == {"source", "query", "limit"}  # type: ignore[attr-defined]
    assert "Cite every fact" in (tool.description or "")  # type: ignore[attr-defined]


def test_describe_error_lists_group_members():
    from agent0.orchestrator.steps import describe_error

    group = ExceptionGroup("all failed", [ValueError("bad schema"), RuntimeError("503 overloaded")])
    text = describe_error(group)
    assert "ValueError: bad schema" in text and "RuntimeError: 503 overloaded" in text
    assert describe_error(KeyError("x" * 1000)).__len__() <= 300


def test_fallback_chain_reaches_every_provider():
    from agent0.models.base import ModelProfile
    from agent0.orchestrator.steps import fallback_chain

    def prof(name, provider):
        return ModelProfile(name=name, provider=provider, model=name, capability="chat", key_env="K")

    ranked = [
        prof("a1", "a"),
        prof("b1", "b"),
        prof("b2", "b"),
        prof("a2", "a"),
        prof("c1", "c"),
        prof("c2", "c"),
    ]
    assert [p.name for p in fallback_chain(ranked)] == ["a1", "b1", "b2", "a2", "c1"]
    assert [p.name for p in fallback_chain(ranked[:2])] == ["a1", "b1"]
