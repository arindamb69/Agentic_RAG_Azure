
import os
import sys
import json
import asyncio
import httpx
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

# Logging setup
DEBUG_LOG_FILE = os.path.join(os.path.dirname(__file__), "mcp_debug.log")

def log_debug(msg):
    try:
        with open(DEBUG_LOG_FILE, "a") as f:
            f.write(f"[MCP-Confluence] {msg}\n")
    except:
        pass

log_debug("Module initialization started.")

# Load environment entries (local dev)
# In production, these should be set in the app environment
current_dir = os.path.dirname(os.path.abspath(__file__))
# Try multiple paths
paths = [
    os.path.join(current_dir, "..", "backend", ".env"),
    os.path.join(current_dir, ".env"),
    os.path.join(os.getcwd(), ".env")
]
for p in paths:
    if os.path.exists(p):
        load_dotenv(dotenv_path=p)
        log_debug(f"Loaded .env from {p}")
        break

# Configuration
CONFLUENCE_URL = os.getenv("CONFLUENCE_URL")
SUBSCRIPTION_KEY = os.getenv("CONFLUENCE_SUBSCRIPTION_KEY")

if not CONFLUENCE_URL or not SUBSCRIPTION_KEY:
    log_debug(f"Error: Missing Config! URL={CONFLUENCE_URL}, SUB_KEY={'*' if SUBSCRIPTION_KEY else 'None'}")
else:
    log_debug(f"Config loaded. URL={CONFLUENCE_URL}")

# Initialize FastMCP Server
mcp = FastMCP("ConfluenceProxy")

# Helper to manage the proxy connection (stateless-ish via HTTP)
async def proxy_tool_call(tool_name: str, arguments: dict):
    """
    Proxies a tool call to the remote MCP server via HTTP POST.
    """
    log_debug(f"Proxying tool call: {tool_name} with args: {arguments}")
    
    if not CONFLUENCE_URL:
        log_debug("No URL configured during call.")
        return "Error: Confluence URL not configured."

    headers = {
        "Ocp-Apim-Subscription-Key": SUBSCRIPTION_KEY,
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        # 1. Initialize to get a session (or just do a stateless call if supported, 
        # but this server seems to want an init handshake first?)
        # Based on tests, we can Initialize -> Call -> Return.
        
        # Initialize
        init_payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "mcp-proxy", "version": "1.0"}
            }
        }
        
        try:
            # We use stream=True to handle potential SSE response, 
            # but we know valid results come in the body or standard JSON for this server.
            # Using standard post for simplicity if it works, or custom logic if we need to parse SSE body.
            resp = await client.post(CONFLUENCE_URL, headers=headers, json=init_payload)
            if resp.status_code != 200:
                msg = f"Error initializing connection: {resp.status_code} {resp.text}"
                log_debug(msg)
                return msg
            
            session_id = resp.headers.get("mcp-session-id")
            if session_id:
                headers["mcp-session-id"] = session_id
                
            # Send Initialized Notification
            await client.post(CONFLUENCE_URL, headers=headers, json={
                "jsonrpc": "2.0",
                "method": "notifications/initialized"
            })
            
            # 2. Call the Tool
            tool_payload = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments
                }
            }
            
            # print(f"Calling remote tool {tool_name}...", file=sys.stderr)
            tool_resp = await client.post(CONFLUENCE_URL, headers=headers, json=tool_payload)
            
            if tool_resp.status_code != 200:
                msg = f"Error calling tool: {tool_resp.status_code} {tool_resp.text}"
                log_debug(msg)
                return msg
            
            # Parse result (Handle SSE body if needed)
            result_data = None
            if "data: " in tool_resp.text:
                for line in tool_resp.text.split('\n'):
                    if line.startswith("data: "):
                        try:
                            data = json.loads(line[6:])
                            if data.get("id") == 2:
                                result_data = data
                                break
                        except: pass
            else:
                try:
                    result_data = tool_resp.json()
                except: pass
            
            # Debugging
            log_debug(f"DEBUG: Parsed result_data keys: {result_data.keys() if result_data else 'None'}")

            if result_data and "result" in result_data:
                # Extract content
                content_list = result_data["result"].get("content", [])
                # Return strictly the text content or valid MCP content structure
                # FastMCP expects us to return a string (Text) or a specialized object.
                # If we return a string, it wraps it in Text.
                texts = []
                for item in content_list:
                    if item.get("type") == "text":
                        texts.append(item.get("text"))
                
                final_text = "\n".join(texts)
                log_debug(f"Returning text of length {len(final_text)}: {final_text[:500]}")
                return final_text
            else:
                log_debug(f"No result returned. Raw body: {tool_resp.text[:500]}")
                return f"No result returned. Raw body: {tool_resp.text[:500]}"
                
        except Exception as e:
            log_debug(f"Exception during proxy call: {e}")
            return f"Exception during proxy call: {e}"

@mcp.tool()
async def search_wiki(query: str) -> str:
    """
    Search Confluence pages using text or CQL. 
    Returns simplified page metadata (ID, title, URL) suitable for follow-up calls to get_page_document.
    """
    # Sanitize query to avoid CQL issues with quotes
    clean_query = query.replace('"', ' ').strip()
    return await proxy_tool_call("search", {"query": clean_query})

@mcp.tool()
async def get_page_document(page_id: str) -> str:
    """
    Retrieve a Confluence page as a single, clean document object.
    Fetches metadata, attachments, and markdown-friendly content.
    This is the PRIMARY tool to read a page.
    """
    return await proxy_tool_call("get_page_document", {"page_id": page_id})

if __name__ == "__main__":
    mcp.run()
