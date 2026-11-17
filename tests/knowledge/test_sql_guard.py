import pytest

from agent0.knowledge.sql import SqlGuardError, SqlKnowledgeSource, validate_select


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT 1",
        "select * from users where id = %s;",
        "WITH t AS (SELECT 1 AS a) SELECT a FROM t",
        "SELECT 'a; DROP TABLE x' AS s",
        "SELECT 'it''s; fine'",
        'SELECT "weird;col" FROM t',
        "SELECT created_at - interval '1 day' FROM t",
    ],
)
def test_accepts_single_reads(sql):
    assert validate_select(sql) == sql


@pytest.mark.parametrize(
    "sql",
    [
        "",
        "   ",
        "INSERT INTO t VALUES (1)",
        "UPDATE t SET a = 1",
        "DELETE FROM t",
        "DROP TABLE t",
        "TRUNCATE t",
        "SELECT 1; DROP TABLE t",
        "SELECT 1; SELECT 2",
        "SELECT 1 -- ; DROP TABLE t",
        "SELECT 1 /* x */",
        "/* x */ DROP TABLE t",
        "SELECT /*! */ 1",
        "WITH d AS (DELETE FROM t RETURNING *) SELECT * FROM d",
        "SELECT * INTO newtable FROM t",
        "SELECT * FROM t FOR UPDATE",
        "SELECT pg_sleep(100)",
        "SELECT set_config('a', 'b', false)",
        "SELECT $$ x $$",
        "SELECT $q$ x $q$",
        "SELECT E'\\'; DROP TABLE t; --'",
        "SELECT 'unterminated",
        "COPY t TO '/tmp/x'",
        "EXPLAIN ANALYZE DELETE FROM t",
        "SELECT 1\x00; DROP TABLE t",
    ],
)
def test_rejects_everything_else(sql):
    with pytest.raises(SqlGuardError):
        validate_select(sql)


async def test_query_builds_stable_records_and_keeps_sql():
    calls = []

    async def executor(sql, params):
        calls.append((sql, list(params)))
        return [{"id": 1, "name": "a"}, {"id": 2, "name": "b"}]

    src = SqlKnowledgeSource("crm", executor=executor)
    first = await src.query("SELECT id, name FROM t WHERE x = %s", [5])
    again = await src.query("SELECT id, name FROM t WHERE x = %s", [5])
    other = await src.query("SELECT id, name FROM t WHERE x = %s", [6])

    assert [r.source_id for r in first] == [r.source_id for r in again]
    assert first[0].source_id.startswith("sql:crm:")
    assert first[0].source_id != first[1].source_id != other[0].source_id
    assert first[0].metadata["sql"] == "SELECT id, name FROM t WHERE x = %s"
    assert first[0].metadata["params"] == [5]
    assert await src.get(first[1].source_id) == first[1]
    assert await src.get("sql:crm:unknown") is None
    assert await src.rerun(first[0]) == first[0]


async def test_query_refuses_before_touching_the_database():
    async def executor(sql, params):
        raise AssertionError("must not run")

    with pytest.raises(SqlGuardError):
        await SqlKnowledgeSource("crm", executor=executor).query("DELETE FROM t")
