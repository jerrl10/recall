"""Recall MCP server entry point.

Keep this layer thin. Business logic belongs in application services.
"""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Recall")


@mcp.tool()
async def health() -> dict[str, str]:
    """Return the MCP server health status."""
    return {"status": "ok"}


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
