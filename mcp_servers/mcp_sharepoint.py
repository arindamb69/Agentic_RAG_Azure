from mcp.server.fastmcp import FastMCP
import os

mcp = FastMCP("SharePointConnector")

@mcp.tool()
async def search_site(query: str) -> str:
    """Searches a SharePoint site for documents and pages."""
    # Real impl would use MS Graph API
    return f"[SharePoint] Found 3 documents matching '{query}':\n1. HR Policy.docx\n2. Q4 Report.pptx\n3. Project Plan.xlsx"

@mcp.tool()
async def get_document_content(doc_id: str) -> str:
    """Retrieves text content from a specific SharePoint document."""
    return f"[SharePoint] Content of document {doc_id}...\n(Simulated content extraction)"

if __name__ == "__main__":
    mcp.run()
