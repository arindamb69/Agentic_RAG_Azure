import asyncio
import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv

# Ensure we can import mcp
try:
    from mcp.client.sse import sse_client
    from mcp.client.session import ClientSession
except ImportError:
    print("Error: 'mcp' package not found. Please install it (pip install mcp).")
    sys.exit(1)

async def main():
    # 1. Load Environment Variables
    # Assuming the script is run from mcp_servers/ or root, look for backend/.env
    current_dir = Path(__file__).parent.resolve()
    # Try multiple locations for .env
    env_paths = [
        current_dir / ".env",
        current_dir.parent / ".env",
        current_dir.parent / "backend" / ".env"
    ]
    
    env_loaded = False
    for path in env_paths:
        if path.exists():
            print(f"Loading .env from: {path}")
            load_dotenv(dotenv_path=path)
            env_loaded = True
            break
    
    if not env_loaded:
        print("Warning: .env file not found.")

    # 2. Get Configuration
    confluence_url = os.getenv("CONFLUENCE_URL")
    subscription_key = os.getenv("CONFLUENCE_SUBSCRIPTION_KEY")
    
    # API Token is not mandatory, but we can verify if it's there casually.
    # The primary auth is the subscription key for this APIM endpoint.
    
    print("\nConfiguration:")
    print(f"  URL: {confluence_url}")
    print(f"  Subscription Key: {'*' * 4 if subscription_key else 'None'}")

    if not confluence_url:
        print("Error: CONFLUENCE_URL is missing.")
        return

    # 3. Setup Headers
    headers = {}
    if subscription_key:
        headers["Ocp-Apim-Subscription-Key"] = subscription_key
    else:
        print("Warning: CONFLUENCE_SUBSCRIPTION_KEY is not set. Connection may fail.") 

    # Remove retry logic, usage exact URL as per instruction
    url = confluence_url
    print(f"\nConnecting to: {url}")

    try:
        async with sse_client(url, headers=headers, timeout=10.0) as (read, write):
            print(f"Connected successfully to {url}!")
            
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                # 4. List Tools
                print("\n--- Available Tools ---")
                tools = await session.list_tools()
                for tool in tools.tools:
                    print(f"Tool: {tool.name}")
                    print(f"  Description: {tool.description}")
                
                # 5. Execute Workflow
                print("\n--- Executing Search & Get Workflow ---")
                
                # Step 1: Search
                search_query = "Tell me about CDC management console setup"
                print(f"1. Searching with query: '{search_query}'")
                
                try:
                    search_result = await session.call_tool("search", arguments={"query": search_query})
                    
                    page_id = None
                    
                    # Inspect results to find a page ID
                    for content in search_result.content:
                        if content.type == "text":
                            print(f"Search Result Raw Output: {content.text[:200]}...") # Print preview
                            
                            # Attempt to parse as JSON to extract ID
                            try:
                                data = json.loads(content.text)
                                # Handle list of results
                                if isinstance(data, list) and len(data) > 0:
                                    # Assuming the first result is relevant
                                    item = data[0]
                                    page_id = item.get("id") or item.get("pageId")
                                    title = item.get("title")
                                    print(f"Found Page: '{title}' (ID: {page_id})")
                                elif isinstance(data, dict):
                                    # Handle object wrapper around results
                                    results = data.get("results", [])
                                    if results:
                                        item = results[0]
                                        page_id = item.get("id") or item.get("pageId")
                                        title = item.get("title")
                                        print(f"Found Page: '{title}' (ID: {page_id})")
                                    else:
                                         # Maybe the dict itself is the page?
                                         page_id = data.get("id")
                            except json.JSONDecodeError:
                                print("Search output is not JSON, attempting regex/string search if needed (skipping for now).")
                    
                    # Step 2: Get Page Document
                    if page_id:
                        print(f"\n2. Fetching document for Page ID: {page_id}")
                        doc_result = await session.call_tool("get_page_document", arguments={"page_id": str(page_id)})
                        
                        print("Document Content:")
                        for content in doc_result.content:
                            if content.type == "text":
                                # Print first 500 chars
                                print(content.text[:1000] + "..." if len(content.text) > 1000 else content.text)
                            else:
                                print(f"[{content.type} content]")
                    else:
                        print("\nCould not extract a valid Page ID from search results. Aborting get_page_document step.")

                except Exception as e:
                    print(f"Error during workflow: {e}")
                    import traceback
                    traceback.print_exc()

    except Exception as e:
        print(f"Connection failed for {url}.")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
