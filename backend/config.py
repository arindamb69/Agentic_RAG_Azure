import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # Azure OpenAI
    AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "")
    AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY", "")
    AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
    AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")

    # Azure AI Search
    AZURE_SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT", "")
    AZURE_SEARCH_KEY = os.getenv("AZURE_SEARCH_KEY", "")
    AZURE_SEARCH_INDEX = os.getenv("AZURE_SEARCH_INDEX", "rag-index")
    
    # Custom Search (Volvo AI Hub)
    SEARCH_PROVIDER = os.getenv("SEARCH_PROVIDER", "azure")
    CUSTOM_SEARCH_URL = os.getenv("CUSTOM_SEARCH_URL", "")
    CUSTOM_SEARCH_API_KEY = os.getenv("CUSTOM_SEARCH_API_KEY", "")

    # Memory (Cosmos DB Mongo API)
    COSMOS_CONNECTION_STRING = os.getenv("COSMOS_CONNECTION_STRING", "")
    COSMOS_DATABASE = os.getenv("COSMOS_DATABASE", "agent_memory")
    COSMOS_COLLECTION = os.getenv("COSMOS_COLLECTION", "conversations")
    COSMOS_DATA_DATABASE = os.getenv("COSMOS_DATA_DATABASE", "agent_data")

    # Redis
    REDIS_HOST = os.getenv("REDIS_HOST", "")
    REDIS_PORT = int(os.getenv("REDIS_PORT", 6380))  # Default to 6380 for Azure Redis SSL
    REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")
    REDIS_SSL = os.getenv("REDIS_SSL", "true").lower() == "true"
    REDIS_USE_ENTRA_ID = os.getenv("REDIS_USE_ENTRA_ID", "false").lower() == "true"

    # MCP Connection Initializers - Blob Storage
    # For Entra ID: use BLOB_ACCOUNT_URL, for connection string: use BLOB_CONNECTION_STRING
    BLOB_ACCOUNT_URL = os.getenv("BLOB_ACCOUNT_URL", "")  # e.g., https://<storage>.blob.core.windows.net
    BLOB_CONNECTION_STRING = os.getenv("BLOB_CONNECTION_STRING", "")
    SQL_CONNECTION_STRING = os.getenv("SQL_CONNECTION_STRING", "")

    # SharePoint
    SHAREPOINT_SITE_URL = os.getenv("SHAREPOINT_SITE_URL", "")
    SHAREPOINT_CLIENT_ID = os.getenv("SHAREPOINT_CLIENT_ID", "")
    SHAREPOINT_CLIENT_SECRET = os.getenv("SHAREPOINT_CLIENT_SECRET", "")

    # Confluence (Cloud or On-Premise)
    CONFLUENCE_URL = os.getenv("CONFLUENCE_URL", "")
    CONFLUENCE_USERNAME = os.getenv("CONFLUENCE_USERNAME", "")
    CONFLUENCE_API_TOKEN = os.getenv("CONFLUENCE_API_TOKEN", "") # Cloud API Token
    CONFLUENCE_PAT = os.getenv("CONFLUENCE_PAT", "") # On-Premise Personal Access Token

settings = Settings()
