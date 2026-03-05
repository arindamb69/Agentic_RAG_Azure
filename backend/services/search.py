import httpx
from azure.search.documents.aio import SearchClient
from azure.core.credentials import AzureKeyCredential
from azure.identity.aio import DefaultAzureCredential
from config import settings

class SearchService:
    def __init__(self):
        self.is_active = False
        self.client = None
        self.provider = settings.SEARCH_PROVIDER
        self.http_client = httpx.AsyncClient(verify=False, timeout=60.0)

        if self.provider == "custom" and settings.CUSTOM_SEARCH_URL:
            self.endpoint = settings.CUSTOM_SEARCH_URL
            self.key = settings.CUSTOM_SEARCH_API_KEY
            self.index = settings.AZURE_SEARCH_INDEX
            self.is_active = True
            print(f"Search Service: Ready using Custom Provider (Volvo AI Hub) at {self.endpoint} [Index: {self.index}]")
        elif settings.AZURE_SEARCH_ENDPOINT:
            self.endpoint = settings.AZURE_SEARCH_ENDPOINT
            self.key = settings.AZURE_SEARCH_KEY
            self.index = settings.AZURE_SEARCH_INDEX
            self.is_active = True
            print(f"Search Service: Ready using Azure AI Search at {self.endpoint} [Index: {self.index}]")
        else:
            print("Search Service: No search configuration found. Running in mock mode.")

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
            if self.provider == "custom":
                # Implementation for Volvo GenAI Hub Search
                # Usually we append the index if not already in URL, 
                # but based on the provided URL, we'll try a standard Search POST
                headers = {
                    "api-key": self.key,
                    "Content-Type": "application/json"
                }
                payload = {
                    "search": query,
                    "top": 5
                }
                
                # If the user wants to specify an index dynamically, 
                # some proxies expect it as a query param or part of the path
                url = self.endpoint
                if "?" not in url:
                    url += f"?index={self.index}"
                else:
                    url += f"&index={self.index}"

                resp = await self.http_client.post(url, json=payload, headers=headers)
                
                if resp.status_code != 200:
                    print(f"Custom Search Error {resp.status_code}: {resp.text}")
                    return f"Error from custom search: {resp.status_code}"
                
                data = resp.json()
                results = data.get('value', [])
                
                context = ""
                for res in results:
                    context += f"Source: {res.get('source', 'Unknown')}\nContent: {res.get('content', '')[:200]}...\n\n"
                return context if context else "No relevant documents found."

            # Standard Azure SDK Implementation
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
