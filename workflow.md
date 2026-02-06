# Agentic RAG Azure - Workflow Documentation

This document outlines the operational flow of the Agentic RAG application, detailing how requests are processed, how caching works, and the decision logic for different data sources (Confluence, Azure Search, Blob Storage, etc.).

## 1. High-Level Architecture

The core of the system is the **Agent Orchestrator**, which manages state, caching, and tool execution.

```mermaid
graph TD
    User[User Request] --> Orchestrator[Agent Orchestrator]
    
    subgraph "Memory & Cache Layer"
        Orchestrator -->|1. Normalize & Check| Redis{Redis Cache}
        Orchestrator -->|2. Retrieve & Save| Cosmos[Cosmos DB Memory]
    end
    
    subgraph "Reasoning Core"
        Orchestrator -->|3. Prompt & History| LLM[Azure OpenAI LLM]
        LLM -->|Decide Tool| Orchestrator
    end
    
    subgraph "Tool Ecosystem (MCP)"
        Orchestrator -->|Execute| AzSearch[Azure AI Search]
        Orchestrator -->|Execute| ConfSearch[Confluence Search]
        Orchestrator -->|Execute| ConfRead[Confluence Read Page]
        Orchestrator -->|Execute| Blob[Blob Storage]
        Orchestrator -->|Execute| SQL[SQL / Cosmos DB]
    end
    
    Orchestrator -->|4. Final Response| User
```

---

## 2. Detailed Workflows

### Scenario A: Cache Hit (Fast Path)
*Optimized for latency and cost. Uses query normalization to handle "Tell me about X" vs "What is X".*

```mermaid
sequenceDiagram
    participant User
    participant Orch as Agent Orchestrator
    participant Redis as Redis Cache
    
    User->>Orch: "Tell me about CDC setup"
    
    Note over Orch: Normalize Query:\n"tell me about cdc setup" -> "cdc setup"
    
    Orch->>Redis: GET query:cdc setup
    Redis-->>Orch: "CDC setup involves..." (Found)
    
    Orch-->>User: Returns Cached Response
    Note over Orch: Tokens Used: 0\nLatency: <50ms
```

### Scenario B: Confluence Documentation Retrieval
*Multi-step reasoning loop to find and read internal docs.*

```mermaid
sequenceDiagram
    participant User
    participant Orch as Agent Orchestrator
    participant LLM as Azure OpenAI
    participant Conf as Confluence MCP
    
    User->>Orch: "How do I configure the management console?"
    Orch->>Redis: Check Cache (Miss)
    
    loop Reasoning Cycle
        Orch->>LLM: Send Query + Tools Schema
        LLM-->>Orch: Call Tool: search_confluence("management console configuration")
        
        Orch->>Conf: Search Pages
        Conf-->>Orch: Returns list: [{id: "123", title: "Console Config"}]
        
        Orch->>LLM: Send Tool Result
        LLM-->>Orch: Call Tool: read_confluence_page("123")
        
        Orch->>Conf: Get Page Content
        Conf-->>Orch: Returns full markdown content...
        
        Orch->>LLM: Send Content
        LLM-->>Orch: Final Answer (Synthesis)
    end
    
    Orch->>User: Stream Response
    Orch->>Redis: Cache Result
```

### Scenario C: General Knowledge / Semantic Search
*Standard RAG pattern using Azure AI Search.*

```mermaid
sequenceDiagram
    participant User
    participant Orch as Agent Orchestrator
    participant LLM as Azure OpenAI
    participant AISearch as Azure AI Search
    
    User->>Orch: "What are the safety protocols?"
    Orch->>Redis: Check Cache (Miss)
    
    Orch->>LLM: Send Query
    LLM-->>Orch: Call Tool: azure_search("safety protocols")
    
    Orch->>AISearch: Vector/Hybrid Search
    AISearch-->>Orch: Returns Top 5 Document Chunks
    
    Orch->>LLM: Send Chunks
    LLM-->>Orch: Final Answer
    
    Orch->>User: Stream Response
```

### Scenario D: Structured Data & External Systems (SQL, Cosmos, SharePoint)
*The Agent dynamically selects the correct tool based on the user's intent, supporting any new MCP server.*

```mermaid
sequenceDiagram
    participant User
    participant Orch as Agent Orchestrator
    participant LLM as Azure OpenAI
    participant SQL as SQL/Cosmos/SharePoint

    User->>Orch: "Show me the logs from last week"
    Orch->>Redis: Check Cache (Miss)

    Orch->>LLM: Send Query
    Note over LLM: Intent Recognition: "logs" -> Structured Query
    LLM-->>Orch: Call Tool: query_cosmos("SELECT * FROM c WHERE...")

    Orch->>SQL: Execute Query
    SQL-->>Orch: Returns JSON Results

    Orch->>LLM: Send Data
    LLM-->>Orch: Final Answer (Synthesis)

    Orch->>User: Stream Response
```

### Scenario E: Multi-Source Fallback (Handling "Not Found")
*Ensures robust behavior when primary sources fail.*

```mermaid
graph TD
    Start[User Query] --> TryConf[Try Confluence Search]
    
    TryConf -->|Found| ReadConf[Read Page] --> Answer
    TryConf -->|Not Found| TryAz[Try Azure Search]
    
    TryAz -->|Found| Answer
    TryAz -->|Not Found| TryBlob[Try Blob Storage]
    
    TryBlob -->|Found| ReadBlob[Read File] --> Answer
    TryBlob -->|Not Found| Fail[System Message]
    
    Fail --> Result["I could not find relevant information in the connected data sources."]
    
    Result -->|Do NOT Cache| User
    Answer -->|Cache Success| User
```

## 3. Configuration & Optimization

The system implements 3 key optimizations:

1.  **Tool Output Pruning**:
    *   `search_confluence` returns minimized JSON (ID, Title, URL) instead of full payloads.
    *   *Benefit*: Saves ~90% of input tokens for search steps.

2.  **Context Management**:
    *   History truncation logic in `AgentOrchestrator` limits extremely long tool outputs from previous turns.
    *   *Benefit*: Prevents crashing context windows in long conversations.

3.  **Conditional Caching**:
    *   Only caches successful responses.
    *   Does NOT cache errors or "data not found" messages to prevent cache poisoning.
