import asyncio
import json
import os
import httpx
from dotenv import load_dotenv

# Load environment variables
load_dotenv(dotenv_path="../backend/.env")

URL = os.getenv("CONFLUENCE_URL")
SUBSCRIPTION_KEY = os.getenv("CONFLUENCE_SUBSCRIPTION_KEY")

HEADERS = {
    "Ocp-Apim-Subscription-Key": SUBSCRIPTION_KEY,
    "Accept": "application/json, text/event-stream",
    "Content-Type": "application/json"
}

async def run_test():
    async with httpx.AsyncClient(timeout=30.0) as client_reader, httpx.AsyncClient(timeout=30.0) as client_writer:
        print(f"Connecting to {URL}...", flush=True)
        
        # 1. Initialize (Start the Session/Stream)
        init_payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0"}
            }
        }
        
    # We must keep the stream open to receive responses
        async with client_reader.stream("POST", URL, headers=HEADERS, json=init_payload) as response:
            print(f"Init Status: {response.status_code}", flush=True)
            
            if response.status_code != 200:
                print(f"Failed to initialize: {response.status_code}", flush=True)
                print(await response.aread(), flush=True)
                return

            # Capture Session ID
            session_id = response.headers.get("mcp-session-id")
            print(f"Session ID: {session_id}", flush=True)
            
            # Prepare headers for subsequent requests
            action_headers = HEADERS.copy()
            if session_id:
                action_headers["mcp-session-id"] = session_id
            
            # Use an Event to signal when to stop or when specific steps are done
            stop_event = asyncio.Event()

            # Reader Task
            async def reader_task():
                print("Reader started...", flush=True)
                try:
                    async for line in response.aiter_lines():
                        if not line: continue
                        # print(f"RAW: {line}")
                        
                        if line.startswith("data: "):
                            data_str = line[6:]
                            try:
                                msg = json.loads(data_str)
                                msg_id = msg.get('id')
                                print(f"Received ID {msg_id}: {msg.get('method') or 'result'}", flush=True)
                                
                                if msg_id == 1:
                                     print(f"Init Result: {json.dumps(msg, indent=2)}", flush=True)

                                # Check for search result
                                if msg_id == 2: # Search
                                    print("Processing Search Result...", flush=True)
                                    content = msg["result"].get("content", [])
                                    # Print snippet
                                    print(f"Content preview: {str(content)[:200]}...", flush=True)
                                    
                                    page_id = None
                                    for item in content:
                                        if item.get("type") == "text":
                                            text = item.get("text", "")
                                            # Try parse JSON
                                            try:
                                                res_data = json.loads(text)
                                                if isinstance(res_data, list) and res_data:
                                                    page_id = res_data[0].get("id") or res_data[0].get("pageId")
                                                    title = res_data[0].get("title")
                                                    print(f"Found Page: {title} ({page_id})", flush=True)
                                                elif isinstance(res_data, dict):
                                                    results = res_data.get("results", [])
                                                    if results:
                                                        page_id = results[0].get("id") or results[0].get("pageId")
                                                        title = results[0].get("title")
                                                        print(f"Found Page: {title} ({page_id})", flush=True)
                                                    else:
                                                        # Maybe dict is the page
                                                        page_id = res_data.get("id")
                                            except: 
                                                pass
                                    
                                    if page_id:
                                        print(f"Found Page ID: {page_id}. Triggering Get Page...", flush=True)
                                        # Trigger get page in background (or signal main thread)
                                        # To keep simple, we can send from main thread if we coordinate, 
                                        # strictly, let's just fire-and-forget here or use a queue.
                                        # Simpler: Call send_message directly here? No, client is shared. 
                                        # Ideally we shouldn't await from reader? httpx client is thread safe? 
                                        # In asyncio, yes, but we need to watch out for loop.
                                        # Let's just set a global var or Event.
                                        # Actually, we can just send.
                                        asyncio.create_task(send_get_page(page_id))
                                    else:
                                        print("No page ID found in search.", flush=True)
                                        stop_event.set()

                                elif msg_id == 3: # Get Page
                                    print("\n--- Page Document Received ---", flush=True)
                                    content = msg["result"].get("content", [])
                                    for item in content:
                                        if item.get("type") == "text":
                                            print(item.get("text")[:500] + "...", flush=True)
                                    stop_event.set()

                            except json.JSONDecodeError:
                                pass
                except Exception as e:
                    print(f"Reader Error: {e}", flush=True)
                    stop_event.set()

            # Helper to parse SSE-like body
            def parse_sse_body(text):
                for line in text.split('\n'):
                    if line.startswith("data: "):
                        try:
                            return json.loads(line[6:])
                        except:
                            pass
                return None

            async def send_message_and_parse(msg):
                print(f"\nSending: {msg.get('method')}", flush=True)
                resp = await client_writer.post(URL, headers=action_headers, json=msg)
                print(f"Status: {resp.status_code}", flush=True)
                
                # Check for SSE data in body
                data = parse_sse_body(resp.text)
                if data:
                    # print(f"Parsed Result: {json.dumps(data, indent=2)}", flush=True)
                    return data
                
                # Fallback if just JSON
                try:
                    return resp.json()
                except:
                    return None

            # Start Reader (Keep it running just in case notifications appear there, but we won't rely on it for results)
            task = asyncio.create_task(reader_task())

            # Send Initialized
            await send_message_and_parse({
                "jsonrpc": "2.0",
                "method": "notifications/initialized"
            })

            # Send Search
            res = await send_message_and_parse({
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "search",
                    "arguments": {"query": "Tell me about CDC management console setup"}
                }
            })

            # Process Search Result
            page_id = None
            if res and "result" in res:
                content = res["result"].get("content", [])
                for item in content:
                    if item.get("type") == "text":
                        text = item.get("text", "")
                        # print(f"Search Result Text: {text[:500]}...", flush=True) # Debug
                        try:
                            data = json.loads(text)
                            if isinstance(data, dict):
                                results = data.get("results", [])
                                print(f"Found {len(results)} search results.", flush=True)
                                
                                # Iterate through results to find the best match
                                for r in results:
                                    r_title = r.get("title", "")
                                    r_id = r.get("id")
                                    print(f"  - [{r_id}] {r_title}", flush=True)
                                    
                                    # Target specific ID if we know it, or title
                                    # User wants: "CDC Management console replication set up" -> 295765494
                                    if r_id == "295765494" or "replication set up" in r_title.lower():
                                        page_id = r_id
                                        print(f"    -> MATCH FOUND!", flush=True)
                                        break
                                
                                # If exact match not found in loop, pick the first one as fallback?
                                # For this test, let's be strict or default to the first if we didn't break
                                if not page_id and results:
                                    print("    -> Exact match not found, picking first result as fallback.", flush=True)
                                    page_id = results[0].get("id")

                        except:
                            pass
            
            if page_id:
                # Get Document
                doc_res = await send_message_and_parse({
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {
                        "name": "get_page_document",
                        "arguments": {"page_id": str(page_id)}
                    }
                })
                
                if doc_res and "result" in doc_res:
                    print("\n--- Document Content ---", flush=True)
                    content = doc_res["result"].get("content", [])
                    for item in content:
                        if item.get("type") == "text":
                            print(item.get("text")[:1000], flush=True)
            
            else:
                print("Could not find Page ID.", flush=True)

            # Cleanup
            stop_event.set()
            task.cancel()


if __name__ == "__main__":
    asyncio.run(run_test())
