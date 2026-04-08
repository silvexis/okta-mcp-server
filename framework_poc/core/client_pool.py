"""Client pool for reusing MCP connections across test layers."""

from typing import Optional
from contextlib import asynccontextmanager

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from framework_poc.core.models import ServerConfig
from framework_poc.core.mcp_client import get_mcp_client


class MCPClientPool:
    """
    Connection pool for MCP client sessions.

    Maintains a single MCP subprocess and client session that can be reused
    across multiple test layers, eliminating redundant authentication cycles.

    Usage:
        async with MCPClientPool(server_config) as pool:
            async with pool.get_client() as client:
                tools = await client.list_tools()
    """

    def __init__(self, server_config: ServerConfig):
        """
        Initialize client pool.

        Args:
            server_config: Server configuration
        """
        self.server_config = server_config
        self._client_cm = None
        self._client = None

    async def __aenter__(self):
        """Initialize the pool and create a single client connection."""
        # Create the client connection
        self._client_cm = get_mcp_client(self.server_config)
        self._client = await self._client_cm.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Clean up the client connection."""
        if self._client_cm is not None:
            await self._client_cm.__aexit__(exc_type, exc_val, exc_tb)
            self._client = None
            self._client_cm = None

    @asynccontextmanager
    async def get_client(self):
        """
        Get the shared client session.

        Returns:
            Yields the shared ClientSession

        Raises:
            RuntimeError: If pool is not initialized
        """
        if self._client is None:
            raise RuntimeError("Client pool not initialized. Use 'async with MCPClientPool(...)' first.")

        yield self._client
