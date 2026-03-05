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
            "description": "Semantic search across the indexed knowledge base. Use this as the FIRST STEP for general questions or when looking for information in unstructured documents/PDFs.",
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
            "description": "Query STRUCTURED/RELATIONAL data from SQL database ONLY (e.g. sales, inventory, revenue, users). Use this if the question involves counting, aggregating, or filtering structured records.",
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
            "description": "List all containers in Azure Blob Storage. Use this to DISCOVER which storage areas exist if the user mentions files, media, or broad storage.",
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
            "description": "List all individual files (blobs) in a specific container. Use this to FIND a specific filename if you don't already have the exact name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "container": {"type": "string", "description": "Container name"},
                    "prefix": {"type": "string", "description": "Optional prefix to filter list"}
                },
                "required": ["container"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_blob",
            "description": "Directly read the raw content of a specific file from storage. Use this AFTER finding a filename via 'list_blobs' or if the user provides an exact path.",
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
            "description": "Query unstructured JSON data/documents in Azure Cosmos DB ONLY. Use this if the user mentions 'collections', 'NoSQL', 'JSON documents', or 'Cosmos'. NOTE: This Cosmos DB environment FULLY SUPPORTS advanced SQL operations like GROUP BY, ORDER BY, COUNT(), SUM(), AVG(), MIN(), MAX(), and spatial functions. Write full server-side queries instead of client-side aggregations.",
            "parameters": {
                "type": "object",
                "properties": {
                    "collection_name": {"type": "string", "description": "The collection/container name to query"},
                    "sql_query": {"type": "string", "description": "SQL-like query, e.g. SELECT c.category, COUNT(1) FROM c GROUP BY c.category"}
                },
                "required": ["collection_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_cosmos_collections",
            "description": "List all collections in the Cosmos DB database. Use this to DISCOVER which NoSQL datasets are available.",
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

    async def process_query(self, query: str, history: list = None, api_key: str = None):
        session_id = "default_session"
        if history is None:
            history = []
        
        print(f"Orchestrator: Processing query '{query}'")
        
        # 1. Save User Message
        self.memory.save_message(session_id, "user", query)

        # 2. Check Cache
        normalized_key = self._normalize_query(query)
        cached_response = self.cache.get(f"query:{normalized_key}")
        if cached_response:
            yield {"type": "thought", "content": "Cache hit! Retrieved response from Redis."}
            yield {"type": "chunk", "content": cached_response}
            yield {"type": "complete", "tokens": 0}
            return

        yield {"type": "thought", "content": "Analyzing request and selecting data sources..."}
        
        system_prompt = (
            "You are an expert Azure Enterprise AI Agent. Your goal is to provide accurate, data-driven answers by orchestrating multiple tools.\n\n"
            "CRITICAL SEARCH & FALLBACK PLANNING RULES:\n"
            "If information is NOT found in `azure_search` (or as a proactive plan when certain keywords are present), follow these strict logic rules:\n"
            "1. CONFLUENCE FALLBACK: If the user asks for documents, documentation, or procedures WITHOUT mentioning the keyword 'file', and `azure_search` has no results, you MUST search Confluence.\n"
            "2. STORAGE FALLBACK: If the user mentions the keyword 'file' (e.g., 'check the file', 'upload file', 'find file xyz'), skip general search or after it fails, you MUST perform storage discovery:\n"
            "   - Step A: `list_blob_containers` to identify the right area.\n"
            "   - Step B: `list_blobs` in likely containers.\n"
            "   - Step C: `read_blob` once you have the name.\n"
            "3. SQL FALLBACK: If the user mentions 'table', 'records', or structured data concepts (revenue, inventory), you MUST check `sql_query`.\n"
            "4. COSMOSDB FALLBACK: If the user mentions 'collection', 'logs', 'items', or 'NoSQL documents', you MUST use `list_cosmos_collections` and `query_cosmos`.\n\n"
            "FORMATTING RULES:\n"
            "- Use code blocks (```language) ONLY for multi-line code, full SQL queries, or JSON data. NEVER wrap single words, names, or short technical terms in backticks.\n"
            "- CRITICAL: When using the `generate_diagram` tool, the tool will return raw code. YOU MUST wrap that returned code inside a standard markdown code block with the correct language identifier (i.e. ```mermaid or ```plantuml) so it renders properly in the UI.\n"
            "- Use **bold** for important names and *italics* for emphasis.\n"
            "- Use double newlines between paragraphs for clear readability.\n"
            "- Be persistent. If one tool fails, reason about where else the data might be and try that tool. Your priority is to exhaust all relevant connected sources before saying 'not found'."
        )

        messages = [{"role": "system", "content": system_prompt}]
        
        # Add history (last 10 turns)
        for msg in history[-10:]:
            content = msg.get('content', '')
            role = msg.get('role', '')
            if role == "tool" and len(content) > 2000:
                content = content[:2000] + "... [Truncated]"
            messages.append({"role": role, "content": content})
        
        # Add current query
        messages.append({"role": "user", "content": query})

        # 4. Agent Reasoning Loop (Multi-Step)
        MAX_ITERATIONS = 8
        
        for iteration in range(MAX_ITERATIONS):
            print(f"Orchestrator: Iteration {iteration + 1}...")
            
            try:
                # Call LLM with Tools
                response = await self.llm.generate_response(messages, tools=TOOLS_SCHEMA, api_key=api_key)
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
        
        # Send in larger chunks of 5-10 chars to simulate typing without breaking newlines/formatting
        chunk_size = 10
        for i in range(0, len(response_text), chunk_size):
            yield {"type": "chunk", "content": response_text[i:i+chunk_size]}
            await asyncio.sleep(0.01)

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
        
        # Estimate tokens based on words
        estimated_tokens = int(len(response_text.split(" ")) * 1.3)
        yield {"type": "complete", "tokens": estimated_tokens}
