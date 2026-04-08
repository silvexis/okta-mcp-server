"""Test case manager for tool discovery and MCP client connection."""

from typing import Optional, List

from framework_poc.core.models import Config, ToolDefinition
from framework_poc.core.mcp_client import get_mcp_client


class TestCaseManager:
    """Manages tool discovery and MCP client connections."""

    def __init__(self, config: Config):
        """
        Initialize test case manager.

        Args:
            config: Framework configuration
        """
        self.config = config

    async def get_tool_definition(self, tool_name: str) -> ToolDefinition:
        """
        Get tool definition from MCP server.

        Args:
            tool_name: Name of the tool to fetch

        Returns:
            ToolDefinition object

        Raises:
            ValueError: If tool not found
        """
        async with self._get_mcp_client() as client:
            tools = (await client.list_tools()).tools
            tool = next((t for t in tools if t.name == tool_name), None)

            if tool is None:
                available_tools = [t.name for t in tools]
                raise ValueError(
                    f"Tool '{tool_name}' not found. Available tools: {', '.join(available_tools)}"
                )

            return ToolDefinition.from_mcp_tool(tool)

    async def list_all_tools(self) -> List[ToolDefinition]:
        """
        List all available tools from MCP server.

        Returns:
            List of ToolDefinition objects
        """
        async with self._get_mcp_client() as client:
            tools = (await client.list_tools()).tools
            return [ToolDefinition.from_mcp_tool(t) for t in tools]

    async def call_tool(
        self,
        tool_name: str,
        params: dict
    ) -> dict:
        """
        Call a tool via MCP.

        Args:
            tool_name: Name of the tool to call
            params: Parameters to pass to the tool

        Returns:
            Tool response as dictionary
        """
        async with self._get_mcp_client() as client:
            response = await client.call_tool(tool_name, params)
            # Convert response to dict if needed
            if hasattr(response, 'content'):
                # MCP response format
                return {
                    "content": response.content,
                    "isError": getattr(response, 'isError', False)
                }
            return response

    @property
    def _get_mcp_client(self):
        """Return the shared MCP client context manager bound to this config."""
        return lambda: get_mcp_client(self.config.server)

    async def verify_connection(self) -> bool:
        try:
            print("[DEBUG verify_connection] calling get_mcp_client...")
            async with self._get_mcp_client() as client:
                print("[DEBUG verify_connection] session open, calling list_tools...")
                result = await client.list_tools()
                tools = result.tools
                print(f"[DEBUG verify_connection] got {len(tools)} tools")
                return len(tools) > 0
        except Exception as e:
            print(f"Connection verification failed: {type(e).__name__}: {e}")
            return False
