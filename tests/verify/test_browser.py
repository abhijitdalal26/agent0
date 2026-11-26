import pytest

from agent0.verify import CheckType, Criterion, VerdictStatus
from agent0.verify.checks import BrowserCheck, ConfigError
from agent0.verify.checks.browser import BrowserUnavailable


def crit(**config):
    return Criterion(id="b1", description="page renders", type=CheckType.BROWSER, config=config)


class FakePage:
    def __init__(self, text="Welcome to the shop", title="Shop", fail_nav=False, missing_selector=False):
        self.text = text
        self._title = title
        self.fail_nav = fail_nav
        self.missing_selector = missing_selector
        self.closed = False
        self.got = None

    async def goto(self, url, *, timeout_ms):
        self.got = url
        if self.fail_nav:
            raise TimeoutError("navigation timeout")

    async def wait_for_selector(self, selector, *, timeout_ms):
        if self.missing_selector:
            raise TimeoutError(f"selector {selector} not found")

    async def inner_text(self, selector):
        return self.text

    async def title(self):
        return self._title

    async def close(self):
        self.closed = True


def check_with(page):
    return BrowserCheck(page_factory=lambda: _ret(page))


async def _ret(page):
    return page


async def test_text_match_passes(ctx_factory):
    page = FakePage()
    v = await check_with(page).run(crit(url="http://app.local", expect_text="Welcome"), ctx_factory())
    assert v.status == VerdictStatus.PASS
    assert page.got == "http://app.local" and page.closed


async def test_missing_text_fails(ctx_factory):
    v = await check_with(FakePage()).run(crit(url="http://x", expect_text="Checkout"), ctx_factory())
    assert v.status == VerdictStatus.FAIL
    assert "Checkout" in v.evidence


async def test_selector_wait_and_timeout(ctx_factory):
    ok = await check_with(FakePage()).run(crit(url="http://x", expect_selector="#cart"), ctx_factory())
    assert ok.status == VerdictStatus.PASS
    bad = await check_with(FakePage(missing_selector=True)).run(
        crit(url="http://x", expect_selector="#cart"), ctx_factory()
    )
    assert bad.status == VerdictStatus.FAIL


async def test_navigation_failure_is_fail_not_error(ctx_factory):
    v = await check_with(FakePage(fail_nav=True)).run(crit(url="http://x"), ctx_factory())
    assert v.status == VerdictStatus.FAIL


async def test_missing_playwright_is_error(ctx_factory):
    async def boom():
        raise BrowserUnavailable("install playwright")

    v = await BrowserCheck(page_factory=boom).run(crit(url="http://x"), ctx_factory())
    assert v.status == VerdictStatus.ERROR
    assert "playwright" in v.evidence


async def test_requires_url(ctx_factory):
    with pytest.raises(ConfigError):
        await check_with(FakePage()).run(crit(expect_text="x"), ctx_factory())
