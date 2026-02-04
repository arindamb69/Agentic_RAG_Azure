# How to Add and Configure MCP Servers

This project uses a modular architecture where data connectors are implemented as **MCP (Model Context Protocol)** servers. This allows each data source (Blob Storage, SQL, SharePoint) to be developed, tested, and maintained independently.

## 1. Create a New MCP Server

Navigate to the `mcp_servers/` directory. Create a new Python file for your connector, e.g., `mcp_sql.py`.

We use the `fastmcp` library for rapid development.

```python
# mcp_servers/mcp_sql.py
from mcp.server.fastmcp import FastMCP
import os

# Initialize the server
mcp = FastMCP("SQLServer")

@mcp.tool()
async def query_database(query_string: str) -> str:
    """Executes a read-only SQL query."""
    # Implement your logic here
    return f"Results for: {query_string}"

if __name__ == "__main__":
    mcp.run()
```

## 2. Configure Environment Variables

Add any necessary credentials to your `backend/.env` file (create it if it doesn't exist).

```env
# backend/.env
AZURE_SQL_CONNECTION_STRING="Driver={ODBC Driver 17 for SQL Server};Server=..."
AZURE_BLOB_CONNECTION_STRING="DefaultEndpointsProtocol=https;..."
```

## 3. Register with Agent Orchestrator

Currently, the `AgentOrchestrator` in `backend/agent_orchestrator.py` manually maps tools. To enable your new MCP server, you need to add a method that interfaces with it.

*Note: In a fully productionized version, you would use an MCP Client to automatically discover tools from running MCP servers. For this MVP, we explicitly define the interface.*

Open `backend/agent_orchestrator.py` and add your tool:

```python
class AgentOrchestrator:
    def __init__(self):
        self.tools = {
            "azure_search": self.tool_azure_search,
            "blob_storage": self.tool_blob_storage,
            "sql_db": self.tool_sql_db, # <--- Add this
        }

    # ... existing code ...

    async def tool_sql_db(self, query: str):
        # Option A: Import directly if running in same process (Simplest for MVP)
        # from mcp_servers.mcp_sql import query_database
        # return await query_database(query)
        
        # Option B: Call as external process (Standard MCP way)
        # In a real scenario, you'd use the mcp-python-sdk client here.
        return f"[SQL Result] Mock result for {query}"
```

## 4. Testing Your MCP Server

You can test your MCP server in isolation using the MCP Inspector or simply by running the script if currently designed that way.

For the `mcp_blob.py` example:
```bash
python mcp_servers/mcp_blob.py
```
(Note: Standard MCP servers communicate over stdio, so running it directly might just wait for input. Use an MCP client to test interactions).
