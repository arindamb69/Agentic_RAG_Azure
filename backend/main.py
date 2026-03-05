import asyncio
import json
import time
from fastapi import FastAPI, Request, File, UploadFile, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, FileResponse, JSONResponse
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel
from agent_orchestrator import AgentOrchestrator
from services.media_service import MediaService
import os

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
    api_key: str = None

orchestrator = AgentOrchestrator()
media_service = MediaService()

@app.get("/")
def read_root():
    return {"status": "Agentic RAG Backend is Running", "docs_url": "/docs"}

@app.post("/chat")
async def chat_endpoint(request: ChatRequest, req_raw: Request):
    # Try to get API key from body or header
    api_key = request.api_key or req_raw.headers.get("X-API-Key")

    async def event_generator():
        start_time = time.time()
        token_count = 0
        
        try:
            async for event in orchestrator.process_query(request.query, request.messages, api_key=api_key):
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

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    content = await file.read()
    result = await media_service.process_file(content, file.filename, file.content_type)
    return result

@app.post("/generate-pdf")
async def generate_pdf(request: Request, background_tasks: BackgroundTasks):
    data = await request.json()
    markdown_content = data.get("markdown", "")
    
    try:
        pdf_path = media_service.generate_pdf(markdown_content)
        
        # Clean up the file after sending
        background_tasks.add_task(os.remove, pdf_path)
        
        return FileResponse(
            pdf_path, 
            media_type='application/pdf', 
            filename=f"response_{int(time.time())}.pdf"
        )
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/generate-audio")
async def generate_audio(request: Request, background_tasks: BackgroundTasks):
    data = await request.json()
    message_content = data.get("text", "")
    
    audio_path = await media_service.text_to_speech(message_content)
    
    if audio_path:
        background_tasks.add_task(os.remove, audio_path)
        return FileResponse(
            audio_path,
            media_type='audio/mpeg',
            filename=f"speech_{int(time.time())}.mp3"
        )
    else:
        return JSONResponse(
            status_code=400, 
            content={"error": "TTS not configured or service unavailable. Please check AZURE_OPENAI_TTS_DEPLOYMENT."}
        )

@app.get("/health")
def health():
    return {"status": "ok"}

