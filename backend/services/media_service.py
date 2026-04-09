import os
import io
from typing import Optional, Dict, Any
import base64
from openai import AsyncAzureOpenAI
import fitz # PyMuPDF
from PIL import Image

class MediaService:
    def __init__(self):
        self.endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        self.api_key = os.getenv("AZURE_OPENAI_API_KEY")
        self.api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
        self.deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
        
        self.client = AsyncAzureOpenAI(
            azure_endpoint=self.endpoint,
            api_key=self.api_key,
            api_version=self.api_version
        )

    async def process_file(self, file_content: bytes, filename: str, content_type: str) -> Dict[str, Any]:
        """Process various file types and return extracted text/insights."""
        ext = filename.split('.')[-1].lower()
        
        if ext in ['pdf']:
            return await self._process_pdf(file_content)
        elif ext in ['png', 'jpg', 'jpeg', 'webp']:
            return await self._process_image(file_content, content_type)
        elif ext in ['txt', 'md', 'csv']:
            return {"text": file_content.decode('utf-8', errors='ignore'), "type": "text"}
        elif ext in ['mp3', 'wav', 'm4a', 'mp4', 'mov', 'avi']:
            return await self._process_audio_video(file_content, filename)
        else:
            return {"error": "Unsupported file format", "type": "error"}

    async def _process_pdf(self, content: bytes) -> Dict[str, Any]:
        try:
            doc = fitz.open(stream=content, filetype="pdf")
            text = ""
            for page in doc:
                text += page.get_text()
            return {"text": text, "type": "pdf", "info": f"PDF with {len(doc)} pages"}
        except Exception as e:
            return {"error": f"PDF processing failed: {str(e)}", "type": "error"}

    async def _process_image(self, content: bytes, content_type: str) -> Dict[str, Any]:
        try:
            # Use GPT-4o Vision for OCR and description
            base64_image = base64.b64encode(content).decode('utf-8')
            
            messages = [
                {
                    "role": "system",
                    "content": "You are an assistant that extracts text and describes images accurately. If there is text, transcribe it. If there are charts/diagrams, explain them."
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Extract all text and summarize this image."},
                        {"type": "image_url", "image_url": {"url": f"data:{content_type};base64,{base64_image}"}}
                    ]
                }
            ]
            
            if "chat/completions" in self.endpoint:
                import httpx
                headers = {
                    "api-key": self.api_key,
                    "Content-Type": "application/json"
                }
                payload = {
                    "messages": messages,
                    "max_completion_tokens": 1000
                }
                async with httpx.AsyncClient(verify=False, timeout=120) as http_client:
                    url = f"{self.endpoint}?api-version={self.api_version}"
                    resp = await http_client.post(url, json=payload, headers=headers)
                    if resp.status_code != 200:
                        raise Exception(f"Image API Error {resp.status_code}: {resp.text}")
                    data = resp.json()
                    insights = data['choices'][0]['message']['content']
            else:
                response = await self.client.chat.completions.create(
                    model=self.deployment,
                    messages=messages,
                    max_completion_tokens=1000
                )
                insights = response.choices[0].message.content
            
            return {"text": insights, "type": "image", "raw_content": base64_image}
        except Exception as e:
            return {"error": f"Image processing failed: {str(e)}", "type": "error"}

    async def _process_audio_video(self, content: bytes, filename: str) -> Dict[str, Any]:
        # Note: Azure OpenAI Whisper deployment is often named 'whisper'
        # This requires the Whisper deployment to be available
        try:
            # For now, let's assume we use a 'whisper' deployment or standard OpenAI API
            # If deployment is not specified, this might fail or need custom endpoint
            
            # Since we might not have a Whisper deployment ready, we'll suggest a fallback
            # but I'll implement the code for it.
            
            # We need to save content to a temporary file because Whisper API usually takes a file pointer
            temp_path = f"temp_{filename}"
            with open(temp_path, "wb") as f:
                f.write(content)
            
            try:
                with open(temp_path, "rb") as f:
                    # Use the 'whisper' model name or deployment name
                    # standard azure openai whisper call:
                    transcription = await self.client.audio.transcriptions.create(
                        model="whisper", # This should be the deployment name
                        file=f
                    )
                return {"text": transcription.text, "type": "audio_video"}
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
        except Exception as e:
            return {"error": f"Transcription failed: {str(e)}. (Ensure 'whisper' deployment exists)", "type": "error"}

    def generate_pdf(self, markdown_content: str) -> str:
        """Generate a PDF from markdown content and return the file path."""
        from fpdf import FPDF
        import time

        class PDF(FPDF):
            def header(self):
                # Use a standard font like Helvetica
                self.set_font('Helvetica', 'B', 15)
                self.cell(0, 10, 'Azure Agent Response', 0, 1, 'C')
                self.ln(10)

            def footer(self):
                self.set_y(-15)
                self.set_font('Helvetica', 'I', 8)
                self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

        pdf = PDF()
        pdf.add_page()
        pdf.set_font("Helvetica", size=11)
        
        # Split by lines and encode to avoid character issues
        # Better: use multi_cell for automatic wrapping
        lines = markdown_content.split('\n')
        for line in lines:
            if not line.strip():
                pdf.ln(5)
                continue
            
            # Clean up text for PDF standard fonts (which are limited)
            # Use 'replace' to avoid crashes on emojis
            clean_line = line.encode('latin-1', 'replace').decode('latin-1')
            pdf.multi_cell(0, 8, txt=clean_line)
        
        pdf_filename = f"response_{int(time.time())}.pdf"
        pdf.output(pdf_filename)
        return pdf_filename

    async def text_to_speech(self, text: str) -> Optional[str]:
        """Convert text to speech using Azure OpenAI (if configured) or return None."""
        try:
            # Try to use Azure OpenAI TTS if deployment is 'tts'
            # Note: Many users name it 'tts-1' or similar
            tts_deployment = os.getenv("AZURE_OPENAI_TTS_DEPLOYMENT", "tts")
            
            # Some versions of AsyncAzureOpenAI might not have audio.speech
            # if the api_version is too old. But let's try.
            response = await self.client.audio.speech.create(
                model=tts_deployment,
                voice="alloy",
                input=text[:4000] # Cap at 4k chars
            )
            
            audio_filename = f"speech_{int(time.time())}.mp3"
            # response.stream_to_file is synchronous in some versions, 
            # or we can read it.
            # Using content is safer for async
            content = await response.read()
            with open(audio_filename, "wb") as f:
                f.write(content)
            
            return audio_filename
        except Exception as e:
            print(f"TTS Error: {e}")
            # Fallback to a simple library if needed, but for now we'll just return None
            # so the main.py can handle the 'not configured' message
            return None
