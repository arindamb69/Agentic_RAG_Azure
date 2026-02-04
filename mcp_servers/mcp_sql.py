from mcp.server.fastmcp import FastMCP

# This is a stub for the SQL Server MCP.
# In a real implementation, you would use pyodbc or sqlalchemy to connect to Azure SQL.

mcp = FastMCP("SQLServer")

@mcp.tool()
async def query_sql(query: str) -> str:
    """Executes a SQL query against the Azure SQL Database."""
    # Placeholder logic
    if "SELECT" in query.upper():
        return f"[SQL Result] Mock data for query: {query}\nRows: 5 returned."
    return "Error: Only SELECT queries allowed."

if __name__ == "__main__":
    mcp.run()
