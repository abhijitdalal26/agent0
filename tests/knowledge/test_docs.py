from agent0.knowledge.docs import InMemoryDocsSource, chunk_text
from agent0.knowledge.registry import load_sources


def _write(root, files):
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")


def test_chunks_split_by_heading_and_size():
    text = "intro\n\n# A\nalpha one\n\n## B\nbeta two\n\n```\n# not a heading\n```\n"
    chunks = chunk_text(text)
    assert [h for h, _ in chunks] == ["", "A", "B"]
    assert "# not a heading" in chunks[2][1]
    long = "word " * 100
    parts = chunk_text(long, max_chars=100)
    assert len(parts) > 3 and all(len(c) <= 100 for _, c in parts)


async def test_ids_stable_across_reingest_and_stale_chunks_dropped(tmp_path):
    _write(tmp_path, {"guide/a.md": "# One\nfirst\n\n# Two\nsecond\n", "b.txt": "plain text"})
    src = InMemoryDocsSource("kb", tmp_path)
    assert await src.ingest() == 3
    ids = sorted(src.chunks)
    assert ids == ["doc:kb:b.txt#0", "doc:kb:guide/a.md#0", "doc:kb:guide/a.md#1"]

    assert await src.ingest() == 3
    assert sorted(src.chunks) == ids

    _write(tmp_path, {"guide/a.md": "# One\nfirst edited\n"})
    await src.ingest()
    assert sorted(src.chunks) == ["doc:kb:b.txt#0", "doc:kb:guide/a.md#0"]
    assert "edited" in (await src.get("doc:kb:guide/a.md#0")).content


async def test_search_returns_cited_records(tmp_path):
    _write(tmp_path, {"a.md": "# Refunds\nrefund window is thirty days\n\n# Shipping\nships in two days\n"})
    src = InMemoryDocsSource("kb", tmp_path)
    await src.ingest()
    hits = await src.search("refund window")
    assert hits[0].source_id == "doc:kb:a.md#0"
    assert hits[0].metadata["heading"] == "Refunds"


def test_registry_loads_docs_and_sql(tmp_path):
    (tmp_path / "config").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "config" / "knowledge.yaml").write_text(
        "sources:\n"
        "  - {name: handbook, kind: docs, path: docs}\n"
        "  - {name: wh, kind: sql, dsn_env: WH_URL, timeout_ms: 1000}\n",
        encoding="utf-8",
    )
    sources = load_sources(tmp_path / "config" / "knowledge.yaml", env={"WH_URL": "postgresql://ro@h/db"})
    assert sources["handbook"].kind == "docs" and sources["wh"].kind == "sql"
    assert load_sources(tmp_path / "missing.yaml") == {}
