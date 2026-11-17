import io
import json

from PIL import Image

from agent0.verify import CheckType, Criterion, VerdictStatus
from agent0.verify.checks import ArtifactCheck

BANNED_CLAIMS = [
    {"pattern": r"\bguarantee(?:d|s)?\b", "label": "guaranteed results"},
    {"pattern": r"\blose \d+\s*(?:lbs?|pounds|kg)\b", "label": "specific weight-loss promise"},
    {"pattern": r"\bcures?\b", "label": "medical claim"},
]
DISCLAIMER = [{"pattern": r"results (?:may )?vary", "label": "'Results may vary' disclaimer"}]


def crit(**config):
    return Criterion(id="a1", description="artifact ok", type=CheckType.ARTIFACT, config=config)


def png(width: int, height: int) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), "white").save(buf, format="PNG")
    return buf.getvalue()


async def test_file_exists(ctx_factory, sandbox):
    box = sandbox(files={"report.md": "# Report"})
    assert (
        await ArtifactCheck().run(crit(path="report.md"), ctx_factory(sandbox=box))
    ).status == VerdictStatus.PASS
    v = await ArtifactCheck().run(crit(path="missing.pdf"), ctx_factory(sandbox=box))
    assert v.status == VerdictStatus.FAIL
    assert "missing.pdf" in v.evidence


async def test_json_schema(ctx_factory, sandbox):
    schema = {
        "type": "object",
        "required": ["name", "price"],
        "properties": {"name": {"type": "string"}, "price": {"type": "number", "minimum": 0}},
    }
    box = sandbox(
        files={
            "good.json": json.dumps({"name": "x", "price": 3}),
            "bad.json": json.dumps({"name": "x", "price": -1}),
            "broken.json": "{not json",
        }
    )
    ctx = ctx_factory(sandbox=box)
    assert (
        await ArtifactCheck().run(crit(path="good.json", json_schema=schema), ctx)
    ).status == VerdictStatus.PASS
    bad = await ArtifactCheck().run(crit(path="bad.json", json_schema=schema), ctx)
    assert bad.status == VerdictStatus.FAIL
    assert "price" in bad.evidence
    broken = await ArtifactCheck().run(crit(path="broken.json", json_schema=schema), ctx)
    assert "not valid JSON" in broken.evidence


async def test_image_dimensions(ctx_factory, sandbox):
    box = sandbox(files={"square.png": png(1080, 1080), "wide.png": png(1200, 628), "fake.png": b"nope"})
    ctx = ctx_factory(sandbox=box)
    spec = {"width": 1080, "height": 1080, "format": "png"}
    assert (await ArtifactCheck().run(crit(path="square.png", image=spec), ctx)).status == VerdictStatus.PASS
    wide = await ArtifactCheck().run(crit(path="wide.png", image=spec), ctx)
    assert wide.status == VerdictStatus.FAIL
    assert "1200x628" in wide.evidence
    fake = await ArtifactCheck().run(crit(path="fake.png", image=spec), ctx)
    assert "not a readable image" in fake.evidence


async def test_max_chars_on_output(ctx_factory):
    v = await ArtifactCheck().run(crit(max_chars=20), ctx_factory("x" * 25))
    assert v.status == VerdictStatus.FAIL
    assert "25 chars" in v.evidence


async def test_compliance_banned_claim_fails_and_quotes_match(ctx_factory, sandbox):
    ad = "Summer special!\nLose 30 lbs guaranteed! Results may vary."
    box = sandbox(files={"ad.txt": ad})
    v = await ArtifactCheck().run(
        crit(path="ad.txt", forbidden_patterns=BANNED_CLAIMS, required_patterns=DISCLAIMER),
        ctx_factory(sandbox=box),
    )
    assert v.status == VerdictStatus.FAIL
    assert "guaranteed results" in v.evidence
    assert "'guaranteed'" in v.evidence
    assert "Lose 30 lbs guaranteed!" in v.evidence
    assert "specific weight-loss promise" in v.evidence


async def test_compliance_missing_disclaimer_fails(ctx_factory):
    ad = "Feel lighter this summer with our coaching plan."
    v = await ArtifactCheck().run(
        crit(forbidden_patterns=BANNED_CLAIMS, required_patterns=DISCLAIMER), ctx_factory(ad)
    )
    assert v.status == VerdictStatus.FAIL
    assert "Results may vary" in v.evidence
    assert "missing" in v.evidence


async def test_compliant_ad_passes(ctx_factory):
    ad = "Feel lighter this summer with our coaching plan. RESULTS MAY VARY."
    v = await ArtifactCheck().run(
        crit(forbidden_patterns=BANNED_CLAIMS, required_patterns=DISCLAIMER, max_chars=125), ctx_factory(ad)
    )
    assert v.status == VerdictStatus.PASS


async def test_plain_string_patterns(ctx_factory):
    v = await ArtifactCheck().run(crit(forbidden_patterns=["miracle"]), ctx_factory("A MIRACLE pill"))
    assert v.status == VerdictStatus.FAIL
    assert "'MIRACLE'" in v.evidence
