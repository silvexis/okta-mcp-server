"""Shared MCP client utilities for the framework."""

import os
from contextlib import asynccontextmanager

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from framework_poc.core.models import ServerConfig  # noqa: E402 (models defines ServerConfig)


class _IgnoreExitCode:
    """
    Wraps stdio_client and suppresses the exception raised when the server
    process exits with a non-zero code.

    The Okta MCP server exits non-zero after each stdio session due to a bug
    in __init__.py (asyncio.run() is called with a non-coroutine return value
    from server.main()). The session itself completes successfully before
    that crash, so we suppress it here to avoid false failures.
    """

    def __init__(self, params: StdioServerParameters):
        self._params = params
        self._cm = None

    async def __aenter__(self):
        print("[DEBUG _IgnoreExitCode.__aenter__] starting stdio_client")
        self._cm = stdio_client(self._params)
        result = await self._cm.__aenter__()
        print("[DEBUG _IgnoreExitCode.__aenter__] stdio_client connected")
        return result

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        print(f"[DEBUG _IgnoreExitCode.__aexit__] exc_type={exc_type}, exc_val={exc_val}")
        try:
            await self._cm.__aexit__(exc_type, exc_val, exc_tb)
            print("[DEBUG _IgnoreExitCode.__aexit__] inner __aexit__ completed cleanly")
        except Exception as e:
            print(f"[DEBUG _IgnoreExitCode.__aexit__] suppressed from stdio_client: {type(e).__name__}: {e}")

        # The ExceptionGroup propagates from ClientSession.__aexit__ when the
        # server subprocess exits non-zero.  Suppress it if every sub-exception
        # is the known "a coroutine was expected, got None" ValueError crash.
        if exc_val is not None and isinstance(exc_val, BaseExceptionGroup):
            non_exit_errors = [
                e for e in exc_val.exceptions
                if not (isinstance(e, ValueError) and "a coroutine was expected" in str(e))
            ]
            if not non_exit_errors:
                print("[DEBUG _IgnoreExitCode.__aexit__] suppressing known server-exit ExceptionGroup")
                return True  # suppress — all sub-exceptions are the known crash
            else:
                print(f"[DEBUG _IgnoreExitCode.__aexit__] NOT suppressing — unexpected sub-errors: {non_exit_errors}")

        return False  # don't suppress other exceptions from the body


def build_server_params(server_config: ServerConfig) -> StdioServerParameters:
    """
    Build StdioServerParameters from config, forwarding the current
    process environment so the MCP subprocess inherits all credentials.
    """
    return StdioServerParameters(
        command=server_config.command,
        args=server_config.args,
        env=os.environ.copy(),
    )


@asynccontextmanager
async def get_mcp_client(server_config: ServerConfig):
    """
    Context manager that yields a connected, initialised MCP ClientSession.

    Handles:
    - Forwarding env vars to the subprocess
    - Suppressing the server's non-zero exit crash on session close

    Usage:
        async with get_mcp_client(config.server) as session:
            tools = await session.list_tools()
    """
    params = build_server_params(server_config)
    async with _IgnoreExitCode(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session
