import asyncio

from mcp import Client
from mcp_server import mcp


async def main():
    async with Client(mcp) as client:
        tools = await client.list_tools()

        print([tool.name for tool in tools.tools])
        result = await client.call_tool("hello", {"name": "小明"})
        print(result.content[0].text)


if __name__ == "__main__":
    asyncio.run(main())