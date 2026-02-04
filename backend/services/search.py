from azure.search.documents.aio import SearchClient
from azure.core.credentials import AzureKeyCredential
from azure.identity.aio import DefaultAzureCredential
from config import settings

class SearchService:
    def __init__(self):
        self.is_active = False
        self.client = None
        if settings.AZURE_SEARCH_ENDPOINT:
            self.endpoint = settings.AZURE_SEARCH_ENDPOINT
            self.key = settings.AZURE_SEARCH_KEY
            self.index = settings.AZURE_SEARCH_INDEX
            self.is_active = True
            print(f"Azure AI Search: Service ready for {self.endpoint}")

    async def _get_client(self):
        if self.client:
            return self.client
        
        if self.key:
            credential = AzureKeyCredential(self.key)
        else:
            credential = DefaultAzureCredential()
            
        self.client = SearchClient(
            endpoint=self.endpoint,
            index_name=self.index,
            credential=credential
        )
        return self.client

    async def search(self, query: str):
        if not self.is_active:
            return "[Mock] Azure AI Search not configured. Found 2 mock docs."
        
        try:
            client = await self._get_client()
            results = await client.search(search_text=query, top=5)
            # Format results
            context = ""
            async for res in results:
                context += f"Source: {res.get('source', 'Unknown')}\nContent: {res.get('content', '')[:200]}...\n\n"
            return context if context else "No relevant documents found."
        except Exception as e:
            print(f"Search Error: {e}")
            return f"Error executing search: {str(e)}"
        finally:
            # We keep the client open for reuse
            pass
