import asyncio
import json
import time
import sys
import os
from services.llm import LLMService
from services.search import SearchService
from services.memory import MemoryService
from services.cache import CacheService

# Add parent directory to path to support mcp_servers imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Pre-defined tools schema for OpenAI
TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "azure_search",
            "description": "Semantic search across the indexed knowledge base. Use this for general questions or when looking for information across many documents.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "sql_query",
            "description": "Query structured data from SQL database (sales, inventory, users).",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "SQL SELECT query"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_diagram",
            "description": "Generate software architecture diagrams from text descriptions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "description": {"type": "string", "description": "Description of the system/flow"},
                    "type": {"type": "string", "enum": ["mermaid", "c4"]}
                },
                "required": ["description"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_sharepoint",
            "description": "Search for documents in SharePoint Online sites.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search keywords"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_confluence",
            "description": "Search Confluence Wiki pages.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "CQL query or keywords"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_blob_containers",
            "description": "List all containers in Azure Blob Storage.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_blobs",
            "description": "List blobs in a specific Azure Blob Storage container.",
            "parameters": {
                "type": "object",
                "properties": {
                    "container": {"type": "string", "description": "Container name"},
                    "prefix": {"type": "string", "description": "Optional prefix to filter blobs"}
                },
                "required": ["container"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_blob",
            "description": "Directly read the raw content of a specific file (blob) from storage. Use this if you have a specific filename or if you need to inspect the details of a file not found in semantic search.",
            "parameters": {
                "type": "object",
                "properties": {
                    "container": {"type": "string", "description": "Container name"},
                    "blob_name": {"type": "string", "description": "Name of the blob to read"}
                },
                "required": ["container", "blob_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_cosmos",
            "description": "Query unstructured JSON data in Azure Cosmos DB NoSQL containers using SQL syntax.",
            "parameters": {
                "type": "object",
                "properties": {
                    "collection_name": {"type": "string", "description": "Container name to query"},
                    "sql_query": {"type": "string", "description": "Cosmos SQL query, e.g. SELECT * FROM c WHERE c.type = 'log'"}
                },
                "required": ["collection_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_cosmos_collections",
            "description": "List all collections in the Cosmos DB database.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    }
]

class AgentOrchestrator:
    def __init__(self):
        self.llm = LLMService()
        self.search = SearchService()
        self.memory = MemoryService()
        self.cache = CacheService()
        from services.cosmos_service import CosmosService
        self.cosmos = CosmosService()

    async def process_query(self, query: str, history: list):
        session_id = "default_session" # In prod, extract from request headers
        
        print(f"Orchestrator: Processing query '{query}'")
        
        # 1. Save User Message
        self.memory.save_message(session_id, "user", query)

        # 2. Check Cache
        cached_response = self.cache.get(f"query:{query}")
        if cached_response:
            print("Orchestrator: Cache hit")
            yield {"type": "thought", "content": "Cache hit! Retrieved response from Redis."}
            yield {"type": "chunk", "content": cached_response}
            yield {"type": "complete", "tokens": 0}
            return

        yield {"type": "thought", "content": "Analyzing request with Azure OpenAI..."}
        
        # 3. Construct Context
        # Flatten history for LLM
        system_prompt = (
            "You are a helpful Azure Agent. You have access to various tools to retrieve information.\n"
            "1. Use 'azure_search' for general knowledge or semantic questions.\n"
            "2. If the user mentions a specific file (like a PDF), or if 'azure_search' returns no results, "
            "you MUST check Azure Blob Storage using 'list_blob_containers', 'list_blobs', and 'read_blob'.\n"
            "3. If you find a relevant file in blob storage, use 'read_blob' to extract its contents."
        )
        messages = [{"role": "system", "content": system_prompt}]
        for msg in history[-5:]: # Simple window
            if msg.get('role') and msg.get('content'):
               messages.append({"role": msg['role'], "content": msg['content']})
        
        # Add current query
        messages.append({"role": "user", "content": query})

        # 4. Agent Reasoning Loop (Simplified)
        response_text = ""
        context_data = ""

        # First LLM Call - Decide Tool
        print("Orchestrator: Calling LLM (Initial)...")
        try:
            llm_response = await self.llm.generate_response(messages, tools=TOOLS_SCHEMA)
            print(f"Orchestrator: LLM responded. Type: {type(llm_response)}")
        except Exception as e:
            print(f"Orchestrator: LLM Call Failed: {e}")
            yield {"type": "chunk", "content": f"Error contacting AI: {e}"}
            return
        
        if hasattr(llm_response, 'tool_calls') and llm_response.tool_calls:
            # First, append the assistant's tool call message
            if hasattr(llm_response, 'to_dict'):
                messages.append(llm_response.to_dict())
            elif hasattr(llm_response, 'model_dump'):
                messages.append(llm_response.model_dump())
            else:
                messages.append(llm_response)

            for tool_call in llm_response.tool_calls:
                try:
                    print(f"Orchestrator: Preparing tool call...")
                    fn_name = tool_call.function.name
                    if isinstance(tool_call.function.arguments, str):
                        fn_args = json.loads(tool_call.function.arguments)
                    else:
                        fn_args = tool_call.function.arguments
                        
                    tool_call_id = getattr(tool_call, 'id', 'call_default')
                    print(f"Orchestrator: Tool {fn_name} args parsed. Sending thought...")
                    
                    yield {"type": "thought", "content": f"Decided to call tool: {fn_name} with {fn_args}"}
                    print(f"Orchestrator: Executing {fn_name}...")
                    
                    tool_result = ""
                    if fn_name == "azure_search":
                        tool_result = await self.search.search(fn_args['query'])
                    elif fn_name == "sql_query":
                        from mcp_servers.mcp_sql import query_sql
                        tool_result = await query_sql(fn_args['query'])
                    elif fn_name == "generate_diagram":
                        from mcp_servers.mcp_architecture import generate_diagram
                        tool_desc = fn_args.get('description', '')
                        tool_type = fn_args.get('type', 'mermaid')
                        tool_result = await generate_diagram(tool_desc, tool_type)
                    elif fn_name == "search_sharepoint":
                        from mcp_servers.mcp_sharepoint import search_site
                        tool_result = await search_site(fn_args['query'])
                    elif fn_name == "search_confluence":
                        from mcp_servers.mcp_confluence import search_wiki
                        tool_result = await search_wiki(fn_args['query'])
                    elif fn_name == "list_blob_containers":
                        from mcp_servers import mcp_blob
                        tool_result = await mcp_blob.list_containers()
                    elif fn_name == "list_blobs":
                        from mcp_servers import mcp_blob
                        tool_result = await mcp_blob.list_blobs(fn_args['container'], fn_args.get('prefix', ''))
                    elif fn_name == "read_blob":
                        from mcp_servers import mcp_blob
                        tool_result = await mcp_blob.read_blob(fn_args['container'], fn_args['blob_name'])
                    elif fn_name == "query_cosmos":
                        tool_result = await self.cosmos.query_collection(fn_args['collection_name'], fn_args.get('sql_query', 'SELECT * FROM c'))
                    elif fn_name == "list_cosmos_collections":
                        tool_result = await self.cosmos.list_collections()
                    
                    print(f"Orchestrator: {fn_name} finished. Chars: {len(str(tool_result))}")
                    yield {"type": "thought", "content": f"Tool '{fn_name}' returned data."}
                    
                    # Append individual tool result message
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "name": fn_name,
                        "content": str(tool_result)
                    })
                except Exception as tool_err:
                    print(f"Orchestrator: Tool {fn_name} failed: {tool_err}")
                    yield {"type": "thought", "content": f"Error calling tool {fn_name}: {tool_err}"}
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "name": fn_name,
                        "content": f"Error: {str(tool_err)}"
                    })

            # Second LLM Call - Synthesize
            print("Orchestrator: Calling LLM (Synthesis)...")
            final_response = await self.llm.generate_response(messages)
            response_text = final_response.content if hasattr(final_response, 'content') else str(final_response)

        else:
            # No tool needed
            print("Orchestrator: No tools needed.")
            response_text = llm_response.content if hasattr(llm_response, 'content') else str(llm_response.get('content', ''))

        # 5. Stream Response
        # If it's real Azure OpenAI, we might not get word-by-word streaming unless we use the stream=True API.
        # For compatibility with our frontend chunking, we simulate it or just send large chunks.
        
        yield {"type": "thought", "content": "Synthesizing final answer..."}
        
        words = response_text.split(" ")
        for word in words:
            yield {"type": "chunk", "content": word + " "}
            await asyncio.sleep(0.02)

        # 6. Save Assistant Message & Cache
        self.memory.save_message(session_id, "assistant", response_text)
        self.cache.set(f"query:{query}", response_text)
        
        yield {"type": "complete", "tokens": len(words) * 1.3} # Est
