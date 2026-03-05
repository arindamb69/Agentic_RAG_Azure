from mcp.server.fastmcp import FastMCP
import pyodbc
import os
import sys

# Add parent directory to path to import from backend
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Initialize MCP Server
mcp = FastMCP("SQLServer")

def get_connection():
    """Establish a connection to the Azure SQL Database."""
    try:
        from backend.config import settings
        conn_str = settings.SQL_CONNECTION_STRING
    except ImportError:
        conn_str = os.getenv("SQL_CONNECTION_STRING", "")
    
    if not conn_str or "your-server" in conn_str:
        raise ValueError("SQL_CONNECTION_STRING is not configured in .env or is using default placeholders.")
    
    return pyodbc.connect(conn_str)

@mcp.tool()
async def query_sql(query: str) -> str:
    """
    Executes a SELECT SQL query against the Azure SQL Database.
    Only read-only (SELECT) queries are allowed for safety.
    """
    # Basic safety check
    if not query.strip().upper().startswith("SELECT"):
        return "Error: Only SELECT queries are allowed for this tool."

    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(query)
        
        # Fetch columns and rows
        columns = [column[0] for column in cursor.description]
        rows = cursor.fetchall()
        
        # Format results as a list of dictionaries (JSON-like structure is better for LLMs)
        results = []
        for row in rows:
            results.append(dict(zip(columns, row)))
            
        conn.close()
        
        if not results:
            return "Query executed successfully but returned 0 rows."
            
        return str(results)
        
    except Exception as e:
        return f"SQL Error: {str(e)}"

@mcp.tool()
async def get_table_schema(table_name: str) -> str:
    """
    Returns the schema (column names and types) for a specific table.
    Useful for understanding the database structure before querying.
    """
    query = f"""
    SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, IS_NULLABLE
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_NAME = '{table_name}'
    """
    return await query_sql(query)

@mcp.tool()
async def list_tables() -> str:
    """
    Lists all user tables in the database.
    """
    query = "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE'"
    return await query_sql(query)

if __name__ == "__main__":
    mcp.run()
