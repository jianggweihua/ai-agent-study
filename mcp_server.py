from mcp.server.mcpserver import MCPServer

mcp = MCPServer("demo")

@mcp.tool()
def hello(name: str):
    return f"你好，{name}"

if __name__ == "__main__":
    mcp.run()