from mcp.server.fastmcp import FastMCP
from azure.storage.blob import BlobServiceClient
from azure.identity import DefaultAzureCredential
import os
import sys
import io
import fitz # PyMuPDF

# Add parent directory to path to import from backend
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Initialize MCP Server
mcp = FastMCP("AzureBlobStorage")

# Initialize Azure Client
# Priority: 1. Entra ID (Account URL), 2. Connection String
blob_service = None

def get_blob_service():
    """Get or initialize the blob service client."""
    global blob_service
    if blob_service:
        return blob_service
    
    # Try to import from backend config first
    try:
        from backend.config import settings
        account_url = settings.BLOB_ACCOUNT_URL
        connection_string = settings.BLOB_CONNECTION_STRING
    except ImportError:
        # Fallback to environment variables
        account_url = os.getenv("BLOB_ACCOUNT_URL", os.getenv("AZURE_STORAGE_ACCOUNT_URL", ""))
        connection_string = os.getenv("BLOB_CONNECTION_STRING", os.getenv("AZURE_STORAGE_CONNECTION_STRING", ""))
    
    # Priority: Connection String, then Entra ID
    if not blob_service and connection_string and connection_string.strip():
        try:
            blob_service = BlobServiceClient.from_connection_string(connection_string)
            print("Blob Storage: Using Connection String")
        except Exception as e:
            print(f"Blob Storage: Connection string failed: {e}")

    if not blob_service and account_url and account_url.strip():
        try:
            blob_service = BlobServiceClient(
                account_url=account_url, 
                credential=DefaultAzureCredential()
            )
            print(f"Blob Storage: Using Entra ID")
        except Exception as e:
            print(f"Blob Storage: Entra ID failed: {e}")
            blob_service = None
    
    return blob_service

@mcp.tool()
async def list_containers() -> str:
    """Lists all containers in the Azure Blob Storage account."""
    service = get_blob_service()
    if not service:
        return "Error: Azure Blob Storage not configured. Set BLOB_ACCOUNT_URL for Entra ID auth or BLOB_CONNECTION_STRING."
    
    try:
        containers = service.list_containers()
        container_names = [c.name for c in containers]
        if not container_names:
            return "No containers found in the storage account."
        return "\n".join(container_names)
    except Exception as e:
        return f"Error listing containers: {str(e)}"

@mcp.tool()
async def read_blob(container: str, blob_name: str) -> str:
    """Reads the content of a specific blob."""
    service = get_blob_service()
    if not service:
        return f"Error: Azure Blob Storage service could not be initialized. Please check your Connection String or Entra ID credentials."
    
    try:
        client = service.get_blob_client(container=container, blob=blob_name)
        content = client.download_blob().readall()
        
        # Check if it's a PDF
        if blob_name.lower().endswith('.pdf'):
            try:
                # Open the binary content in-memory with PyMuPDF
                pdf_stream = io.BytesIO(content)
                doc = fitz.open(stream=pdf_stream, filetype="pdf")
                text = ""
                # Get first 10 pages to avoid overwhelming the context window
                for page in doc[:10]:
                    text += page.get_text()
                doc.close()
                return text if text.strip() else "The PDF appears to be empty or contain only images (OCR not supported yet)."
            except Exception as pdf_err:
                return f"Error parsing PDF: {str(pdf_err)}"

        # Try to decode as UTF-8 for other files
        try:
            return content.decode('utf-8')
        except UnicodeDecodeError:
            return f"Binary blob ({len(content)} bytes). Cannot display as text."
    except Exception as e:
        error_msg = str(e)
        if "AuthorizationPermissionMismatch" in error_msg:
            return "Error: Authorization Permission Mismatch. Please ensure your identity has the 'Storage Blob Data Reader' role assigned to the storage account or container in the Azure Portal."
        return f"Error reading blob: {error_msg}"

@mcp.tool()
async def list_blobs(container: str, prefix: str = "") -> str:
    """Lists blobs in a container, optionally filtered by prefix."""
    service = get_blob_service()
    if not service:
        return f"Error: Azure Blob Storage not configured."
    
    try:
        container_client = service.get_container_client(container)
        blobs = container_client.list_blobs(name_starts_with=prefix if prefix else None)
        blob_names = [b.name for b in blobs]
        if not blob_names:
            return f"No blobs found in container '{container}'" + (f" with prefix '{prefix}'" if prefix else "")
        return "\n".join(blob_names)
    except Exception as e:
        error_msg = str(e)
        if "AuthorizationPermissionMismatch" in error_msg:
            return "Error: Authorization Permission Mismatch. Please ensure your identity has the 'Storage Blob Data Reader' role assigned to the storage account or container in the Azure Portal."
        return f"Error listing blobs: {error_msg}"

if __name__ == "__main__":
    mcp.run()
