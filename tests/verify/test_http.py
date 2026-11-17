import httpx

from agent0.verify import CheckType, Criterion, VerdictStatus
from agent0.verify.checks import HttpCheck


def crit(**config):
    return Criterion(id="h1", description="page is up", type=CheckType.HTTP, config=config)


def handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/ok":
        return httpx.Response(200, text="<h1>Welcome to the shop</h1>")
    if request.url.path == "/down":
        raise httpx.ConnectError("connection refused", request=request)
    return httpx.Response(500, text="Internal Server Error")


CHECK = HttpCheck(transport=httpx.MockTransport(handler))


async def test_status_and_text_pass(ctx_factory):
    v = await CHECK.run(crit(url="http://app.local/ok", expect_text="Welcome"), ctx_factory())
    assert v.status == VerdictStatus.PASS


async def test_wrong_status_fails(ctx_factory):
    v = await CHECK.run(crit(url="http://app.local/broken"), ctx_factory())
    assert v.status == VerdictStatus.FAIL
    assert "500" in v.evidence
    accepted = await CHECK.run(crit(url="http://app.local/broken", expect_status=[200, 500]), ctx_factory())
    assert accepted.status == VerdictStatus.PASS


async def test_missing_text_fails(ctx_factory):
    v = await CHECK.run(crit(url="http://app.local/ok", expect_text="Checkout"), ctx_factory())
    assert v.status == VerdictStatus.FAIL
    assert "Checkout" in v.evidence


async def test_unreachable_fails(ctx_factory):
    v = await CHECK.run(crit(url="http://app.local/down"), ctx_factory())
    assert v.status == VerdictStatus.FAIL
    assert "ConnectError" in v.evidence
