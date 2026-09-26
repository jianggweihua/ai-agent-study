from mcp import Client
from mcp_server import mcp


async def call_mcp_hello(name: str):
    async with Client(mcp) as client:
        result = await client.call_tool("hello", {"name": name})
        return result.content[0].text