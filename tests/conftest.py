import asyncio
import sys

if sys.platform == "win32":

    def pytest_asyncio_loop_factories(config, item):
        # psycopg async cannot run on the Windows Proactor loop.
        return {"selector": asyncio.SelectorEventLoop}
