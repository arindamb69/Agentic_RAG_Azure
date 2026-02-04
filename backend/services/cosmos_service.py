from azure.cosmos import CosmosClient, PartitionKey
import json
from config import settings

class CosmosService:
    def __init__(self):
        self.is_active = False
        self.client = None
        if settings.COSMOS_CONNECTION_STRING:
            try:
                # Use NoSQL SDK from connection string
                self.client = CosmosClient.from_connection_string(settings.COSMOS_CONNECTION_STRING)
                self.database = self.client.get_database_client(settings.COSMOS_DATA_DATABASE)
                self.is_active = True
                print(f"Cosmos DB (NoSQL): Connected to database '{settings.COSMOS_DATA_DATABASE}'")
            except Exception as e:
                print(f"Cosmos DB Connection Error: {e}")
                self.is_active = False

    async def query_collection(self, collection_name: str, query_sql: str, parameters: list = None):
        """
        Query NoSQL data in Azure Cosmos DB using SQL.
        Example query_sql: "SELECT * FROM c WHERE c.category = 'electronics'"
        """
        if not self.is_active:
            return "Error: Cosmos DB not configured or connection failed."
        
        try:
            container = self.database.get_container_client(collection_name)
            # NoSQL API uses SQL-like queries
            results = container.query_items(
                query=query_sql,
                parameters=parameters,
                enable_cross_partition_query=True
            )
            
            output = []
            for item in results:
                # Items are dicts in NoSQL SDK
                output.append(item)
            
            if not output:
                return f"No items found in '{collection_name}' matching query."
            
            return json.dumps(output, indent=2, default=str)
        except Exception as e:
            return f"Error querying Cosmos DB: {str(e)}"

    async def insert_document(self, collection_name: str, document: dict):
        if not self.is_active:
            return "Error: Cosmos DB not configured."
        
        try:
            container = self.database.get_container_client(collection_name)
            # Ensure document has an 'id'
            if 'id' not in document:
                import uuid
                document['id'] = str(uuid.uuid4())
                
            result = container.upsert_item(document)
            return f"Successfully inserted document with ID: {result.get('id')}"
        except Exception as e:
            return f"Error inserting into Cosmos DB: {str(e)}"

    async def list_collections(self):
        """Lists containers in the NoSQL database."""
        if not self.is_active:
            return "Error: Cosmos DB not configured."
        try:
            return [container['id'] for container in self.database.list_containers()]
        except Exception as e:
            return f"Error listing containers: {str(e)}"
