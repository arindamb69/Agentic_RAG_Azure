from mcp.server.fastmcp import FastMCP

mcp = FastMCP("ConfluenceConnector")

@mcp.tool()
async def search_wiki(cql_query: str) -> str:
    """Searches Confluence (Cloud or Data Center) using CQL."""
    return f"[Confluence] Pages matching '{cql_query}':\n1. Engineering Onboarding\n2. API Spec v2\n3. Release Notes"

@mcp.tool()
async def get_page(page_id: str) -> str:
    """Reads a Confluence page."""
    return f"[Confluence] Page {page_id} contains...\n(Simulated Wiki Content)"

if __name__ == "__main__":
    mcp.run()
