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

The `AgentOrchestrator` in `backend/agent_orchestrator.py` uses a **Tool Schema** and a **Dispatch Loop** to manage MCP matches.

1. **Add to `TOOLS_SCHEMA`**: Define the tool's interface so the LLM knows how to call it.

```python
# backend/agent_orchestrator.py
TOOLS_SCHEMA = [
    # ... existing tools ...
    {
        "type": "function",
        "function": {
            "name": "query_database", # Name of your tool
            "description": "Executes a read-only SQL query.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query_string": {"type": "string", "description": "SQL query to run"}
                },
                "required": ["query_string"]
            }
        }
    }
]
```

2. **Add to Dispatch Logic**: Update the `process_query` method to handle the new tool name.

```python
# backend/agent_orchestrator.py

# Inside the 'for tool_call in response.tool_calls:' loop:
elif fn_name == "query_database":
    from mcp_servers.mcp_sql import query_database
    tool_result = await query_database(fn_args['query_string'])
```

*Note: For this MVP, we are importing the functions directly (`from mcp_servers...`) to run them in the same process, rather than spawning separate stdio processes.*

## 4. Testing Your MCP Server

You can test your MCP server in isolation using the MCP Inspector or simply by running the script if currently designed that way.

For the `mcp_blob.py` example:
```bash
python mcp_servers/mcp_blob.py
```
(Note: Standard MCP servers communicate over stdio, so running it directly might just wait for input. Use an MCP client to test interactions).
