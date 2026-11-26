from __future__ import annotations

import asyncio
import threading
from collections.abc import Awaitable, Callable, Coroutine
from typing import Any, Protocol

from agent0.verify.base import CheckType, Criterion, Verdict, VerdictStatus, VerifyContext
from agent0.verify.checks._util import CheckStage, head, require, verdict


class BrowserPage(Protocol):
    async def goto(self, url: str, *, timeout_ms: int) -> None: ...

    async def wait_for_selector(self, selector: str, *, timeout_ms: int) -> None: ...

    async def inner_text(self, selector: str) -> str: ...

    async def title(self) -> str: ...

    async def close(self) -> None: ...


PageFactory = Callable[[], Awaitable[BrowserPage]]


class BrowserUnavailable(RuntimeError):
    pass


class _ThreadedPage:
    """Drives Playwright on a dedicated thread with its own event loop.

    The API server runs under a SelectorEventLoop (psycopg needs it), and Playwright's
    pipe transport on Windows requires ProactorEventLoop — so the browser lives on its
    own thread rather than the caller's loop.
    """

    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._pw: Any = None
        self._browser: Any = None
        self._page: Any = None

    def _submit(self, coro: Coroutine[Any, Any, Any]) -> asyncio.Future[Any]:
        return asyncio.wrap_future(asyncio.run_coroutine_threadsafe(coro, self._loop))

    async def start(self) -> None:
        self._thread.start()

        async def boot() -> None:
            try:
                from playwright.async_api import async_playwright
            except ImportError as exc:
                raise BrowserUnavailable(
                    "browser checks need Playwright: `uv sync --extra browser`, "
                    "then `uv run playwright install chromium`"
                ) from exc
            self._pw = await async_playwright().start()
            self._browser = await self._pw.chromium.launch()
            self._page = await self._browser.new_page()

        try:
            await self._submit(boot())
        except Exception:
            await self.aclose()
            raise

    async def goto(self, url: str, *, timeout_ms: int) -> None:
        await self._submit(self._page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded"))

    async def wait_for_selector(self, selector: str, *, timeout_ms: int) -> None:
        await self._submit(self._page.wait_for_selector(selector, timeout=timeout_ms))

    async def inner_text(self, selector: str) -> str:
        return await self._submit(self._page.inner_text(selector))

    async def title(self) -> str:
        return await self._submit(self._page.title())

    async def aclose(self) -> None:
        async def shutdown() -> None:
            if self._browser is not None:
                await self._browser.close()
            if self._pw is not None:
                await self._pw.stop()

        try:
            await self._submit(shutdown())
        finally:
            self._loop.call_soon_threadsafe(self._loop.stop)
            self._thread.join(timeout=10)
            self._loop.close()

    async def close(self) -> None:
        await self.aclose()


async def _chromium_page() -> BrowserPage:
    page = _ThreadedPage()
    await page.start()
    return page


class BrowserCheck:
    """Loads a real page in headless Chromium and checks what a user would see.

    Config: `url` (required), `expect_text`, `expect_selector`, `wait_ms`, `timeout_s`.
    """

    type = CheckType.BROWSER
    stage = CheckStage.DETERMINISTIC

    def __init__(self, page_factory: PageFactory | None = None) -> None:
        self._factory = page_factory or _chromium_page

    async def run(self, criterion: Criterion, ctx: VerifyContext) -> Verdict:
        url = str(require(criterion, "url"))
        cfg = criterion.config
        timeout_ms = int(float(cfg.get("timeout_s", 20)) * 1000)
        try:
            page = await self._factory()
        except BrowserUnavailable as exc:
            return verdict(criterion, VerdictStatus.ERROR, str(exc))
        try:
            try:
                await page.goto(url, timeout_ms=timeout_ms)
                selector = cfg.get("expect_selector")
                if selector:
                    await page.wait_for_selector(str(selector), timeout_ms=timeout_ms)
                if wait_ms := int(cfg.get("wait_ms", 0)):
                    await asyncio.sleep(wait_ms / 1000)
            except Exception as exc:
                return verdict(
                    criterion,
                    VerdictStatus.FAIL,
                    f"{url} did not reach the expected state: {type(exc).__name__}: {exc}",
                )
            title = await page.title()
            text = await page.inner_text("body")
        finally:
            await page.close()

        needle = cfg.get("expect_text")
        where = f'"{title}"' if title else url
        if needle and str(needle) not in text:
            return verdict(
                criterion,
                VerdictStatus.FAIL,
                f"{where} loaded, but visible text does not contain {needle!r}.\n{head(text, 500)}",
            )
        matched = f" found {needle!r}" if needle else ""
        return verdict(criterion, VerdictStatus.PASS, f"{where}{matched} ({len(text)} chars visible)")
