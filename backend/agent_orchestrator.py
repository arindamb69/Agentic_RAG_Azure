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
            "name": "read_confluence_page",
            "description": "Read the full content of a Confluence page using its Page ID. Use this after finding a page ID via 'search_confluence'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "page_id": {"type": "string", "description": "The ID of the page to read"}
                },
                "required": ["page_id"]
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

    def _normalize_query(self, query: str) -> str:
        """Normalizes query for better cache hit rates."""
        # Lowercase and strip whitespace
        q = query.lower().strip()
        
        # Remove common prefixes
        prefixes = [
            "tell me about", "what is", "how do i", "how to", "what do you know about", 
            "explain", "show me", "can you tell me about", "search for"
        ]
        
        for prefix in prefixes:
            if q.startswith(prefix):
                q = q[len(prefix):].strip()
                break # Only remove one prefix
                
        # Remove punctuation from end
        return q.rstrip("?.!")

    async def process_query(self, query: str, history: list):
        session_id = "default_session" # In prod, extract from request headers
        
        print(f"Orchestrator: Processing query '{query}'")
        
        # 1. Save User Message
        self.memory.save_message(session_id, "user", query)

        # 2. Check Cache with Normalized Key
        normalized_key = self._normalize_query(query)
        print(f"Orchestrator: Checking cache for key 'query:{normalized_key}'")
        
        cached_response = self.cache.get(f"query:{normalized_key}")
        if cached_response:
            print("Orchestrator: Cache hit")
            yield {"type": "thought", "content": "Cache hit! Retrieved response from Redis."}
            yield {"type": "chunk", "content": cached_response}
            yield {"type": "complete", "tokens": 0}
            return

        yield {"type": "thought", "content": "Analyzing request with Azure OpenAI..."}
        
        # 3. Construct Context (Optimized with Summarization)
        # Instead of sending all raw history, we ideally summarize older turns.
        # For this implementation, we will perform a lightweight truncation/selection
        # to ensure we don't blow up the context window with large tool outputs from previous turns.
        
        system_prompt = (
            "You are a helpful Azure Agent. You have access to various tools to retrieve information.\n"
            "Retrieval Strategy:\n"
            "1. Use 'azure_search' for general knowledge or semantic questions.\n"
            "2. Use 'search_confluence' for technical documentation, setup guides, wikis, and verified internal procedures.\n"
            "   - CRITICAL: If 'search_confluence' returns a list of pages, you MUST select the most relevant Page ID and IMMEDIATELY call 'read_confluence_page' to read its content. The search result alone is NOT enough to answer.\n"
            "3. If the user mentions a specific file (like a PDF), or if other searches return no results, "
            "check Azure Blob Storage using 'list_blob_containers', 'list_blobs', and 'read_blob'.\n"
            "4. If you find a relevant file in blob storage, use 'read_blob' to extract its contents.\n"
            "5. IMPORTANT: You must ONLY answer based on the information retrieved from the tools (Search, SQL, Confluence, Blob Storage).\n"
            "   - If the tools return relevant information, use it to answer.\n"
            "   - If a tool returns an Error (e.g., connection failed, timeout), please report this technical issue to the user so they are aware.\n"
            "   - If the tools run successfully but return no results or irrelevant information, try another source. If ALL sources fail, simply state: 'I could not find relevant information in the connected data sources.'\n"
            "   - Do NOT use your internal training data to answer if the tools fail or find nothing."
        )
        
        messages = [{"role": "system", "content": system_prompt}]
        
        # Optimization: Filter and truncate history
        for msg in history[-5:]: 
            content = msg.get('content', '')
            role = msg.get('role', '')
            
            # Truncate very long tool outputs in history to save tokens
            if role == "tool" and len(content) > 2000:
                content = content[:2000] + "... [Truncated for Context Optimization]"
            
            # Truncate long assistant messages if they are just data dumps
            if role == "assistant" and len(content) > 3000:
                content = content[:3000] + "... [Truncated]"

            if content:
               messages.append({"role": role, "content": content})
        
        # Add current query
        messages.append({"role": "user", "content": query})

        # 4. Agent Reasoning Loop (Multi-Step)
        MAX_ITERATIONS = 5
        response_text = ""
        
        for iteration in range(MAX_ITERATIONS):
            print(f"Orchestrator: Iteration {iteration + 1}...")
            
            try:
                # Call LLM with Tools
                response = await self.llm.generate_response(messages, tools=TOOLS_SCHEMA)
            except Exception as e:
                print(f"Orchestrator: LLM Call Failed: {e}")
                yield {"type": "chunk", "content": f"Error contacting AI: {e}"}
                return

            # Check if LLM wants to call tools
            if hasattr(response, 'tool_calls') and response.tool_calls:
                print(f"Orchestrator: LLM requested {len(response.tool_calls)} tool calls.")
                
                # Add assistant message with tool calls to history
                if hasattr(response, 'to_dict'):
                    messages.append(response.to_dict())
                elif hasattr(response, 'model_dump'):
                    messages.append(response.model_dump())
                else:
                    messages.append(response)

                # Execute each tool
                for tool_call in response.tool_calls:
                    tool_result = ""
                    try:
                        fn_name = tool_call.function.name
                        if isinstance(tool_call.function.arguments, str):
                            fn_args = json.loads(tool_call.function.arguments)
                        else:
                            fn_args = tool_call.function.arguments
                            
                        tool_call_id = getattr(tool_call, 'id', 'call_default')
                        
                        yield {"type": "thought", "content": f"Decided to call tool: {fn_name} with {fn_args}"}
                        print(f"Orchestrator: Executing {fn_name}...")
                        
                        # --- Tool Dispatch ---
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
                        elif fn_name == "read_confluence_page":
                             from mcp_servers.mcp_confluence import get_page_document
                             tool_result = await get_page_document(fn_args['page_id'])
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
                        
                        print(f"Orchestrator: Tool {fn_name} finished. Chars: {len(str(tool_result))}")
                        yield {"type": "thought", "content": f"Tool '{fn_name}' returned data."}

                    except Exception as tool_err:
                        print(f"Orchestrator: Tool {fn_name} failed: {tool_err}")
                        yield {"type": "thought", "content": f"Error calling tool {fn_name}: {tool_err}"}
                        tool_result = f"Error: {str(tool_err)}"

                    # Append tool result to history
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "name": fn_name,
                        "content": str(tool_result)
                    })
                
                # Loop continues to next iteration to let LLM see results and decide next step
            
            else:
                # No tools requested -> Final Answer
                print("Orchestrator: No tools requested. Finalizing answer.")
                response_text = response.content if hasattr(response, 'content') else str(response.get('content', ''))
                break

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
        
        # Optimization: Only cache valid, useful responses.
        # Do NOT cache if the response indicates failure, "not found", or an error.
        error_indicators = [
            "could not find relevant information", 
            "technical issue", 
            "Error contacting AI",
            "Error calling tool"
        ]
        
        should_cache = True
        for err in error_indicators:
            if err in response_text:
                should_cache = False
                break
        
        if should_cache:
            print(f"Orchestrator: Caching successful response for '{query}' (Key: {normalized_key})")
            self.cache.set(f"query:{normalized_key}", response_text)
        else:
            print(f"Orchestrator: Skipping cache for failed/empty response.")
        
        yield {"type": "complete", "tokens": len(words) * 1.3} # Est
