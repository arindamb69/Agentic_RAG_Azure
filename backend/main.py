import asyncio
import json
import time
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel
from agent_orchestrator import AgentOrchestrator

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    query: str
    messages: list = []

orchestrator = AgentOrchestrator()

@app.get("/")
def read_root():
    return {"status": "Agentic RAG Backend is Running", "docs_url": "/docs"}

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    async def event_generator():
        start_time = time.time()
        token_count = 0
        
        try:
            async for event in orchestrator.process_query(request.query, request.messages):
                # event is a dict: type, content
                event_type = event.get("type")
                
                if event_type == "chunk":
                    yield {"data": json.dumps(event)}
                    token_count += 1 # Rough estimation
                elif event_type == "complete":
                    # Don't send the original complete event - send metrics first, then complete
                    yield {"data": json.dumps({
                        "type": "metrics",
                        "duration_ms": int((time.time() - start_time) * 1000),
                        "tokens": event.get("tokens", token_count)
                    })}
                    yield {"data": json.dumps({"type": "complete"})}
                else:
                    # Send other events (thought, etc.) as-is
                    yield {"data": json.dumps(event)}
        except Exception as e:
            yield {"data": json.dumps({"type": "error", "content": str(e)})}
            
    return EventSourceResponse(event_generator())

@app.get("/health")
def health():
    return {"status": "ok"}
