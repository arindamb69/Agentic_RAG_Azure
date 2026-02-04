from azure.cosmos import CosmosClient, PartitionKey
from config import settings
import datetime
import uuid

class MemoryService:
    def __init__(self):
        self.use_cosmos = False
        self.memory_store = {} # In-memory fallback
        
        if settings.COSMOS_CONNECTION_STRING:
            try:
                self.client = CosmosClient.from_connection_string(settings.COSMOS_CONNECTION_STRING)
                self.database = self.client.get_database_client(settings.COSMOS_DATABASE)
                self.container = self.database.get_container_client(settings.COSMOS_COLLECTION)
                self.use_cosmos = True
                print(f"Memory Service: Connected to Cosmos DB (NoSQL) Database: {settings.COSMOS_DATABASE}")
            except Exception as e:
                print(f"Failed to connect to Cosmos DB: {e}. Falling back to in-memory.")

    def save_message(self, session_id, role, content):
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.datetime.utcnow().isoformat()
        }
        
        if self.use_cosmos:
            try:
                # In NoSQL API, we treat session_id as the document ID
                try:
                    doc = self.container.read_item(item=session_id, partition_key=session_id)
                except Exception:
                    # New session
                    doc = {"id": session_id, "messages": []}
                
                doc["messages"].append(message)
                self.container.upsert_item(doc)
            except Exception as e:
                print(f"Error saving to Cosmos Memory: {e}")
        else:
            if session_id not in self.memory_store:
                self.memory_store[session_id] = []
            self.memory_store[session_id].append(message)

    def get_history(self, session_id, limit=10):
        if self.use_cosmos:
            try:
                doc = self.container.read_item(item=session_id, partition_key=session_id)
                return doc.get("messages", [])[-limit:]
            except Exception:
                return []
        else:
            return self.memory_store.get(session_id, [])[-limit:]
