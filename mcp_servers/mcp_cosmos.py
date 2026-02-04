from mcp.server.fastmcp import FastMCP
import sys
import os

# Add parent directory to path to import from backend
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.services.cosmos_service import CosmosService

mcp = FastMCP("AzureCosmosDB")
cosmos = CosmosService()

@mcp.tool()
async def query_unstructured_data(container_name: str, sql_query: str = "SELECT * FROM c") -> str:
    """
    Query unstructured data in Azure Cosmos DB using SQL (NoSQL API).
    :param container_name: The name of the container/collection to query.
    :param sql_query: A SQL query string (e.g., "SELECT * FROM c WHERE c.category = 'electronics'").
    """
    return await cosmos.query_collection(container_name, sql_query)

@mcp.tool()
async def list_cosmos_collections() -> str:
    """List all collections available in the Cosmos DB data database."""
    cols = await cosmos.list_collections()
    if isinstance(cols, list):
        return "\n".join(cols) if cols else "No collections found."
    return cols

@mcp.tool()
async def insert_unstructured_data(collection_name: str, document_json: str) -> str:
    """
    Insert a document into a Cosmos DB collection.
    :param collection_name: Target collection.
    :param document_json: JSON string of the document to insert.
    """
    import json
    try:
        doc = json.loads(document_json)
    except Exception:
        return "Error: document_json must be a valid JSON string."
    
    return await cosmos.insert_document(collection_name, doc)

if __name__ == "__main__":
    mcp.run()
