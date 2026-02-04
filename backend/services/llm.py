from openai import AsyncAzureOpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from config import settings
import json
import httpx

class LLMService:
    def __init__(self):
        # Create a custom HTTP client to bypass SSL verification (fix for corporate proxy)
        # Added timeout to prevent connection timeouts
        self.http_client = httpx.AsyncClient(verify=False, timeout=180.0)

        if settings.AZURE_OPENAI_ENDPOINT:
            if settings.AZURE_OPENAI_API_KEY:
                self.client = AsyncAzureOpenAI(
                    azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
                    api_key=settings.AZURE_OPENAI_API_KEY,
                    api_version=settings.AZURE_OPENAI_API_VERSION,
                    http_client=self.http_client
                )
            
            # Check if headers are needed for custom proxies (some don't accept Bearer)
            # Logic: If endpoint ends in /chat/completions, we switch to a Direct HTTP mode
            if "chat/completions" in settings.AZURE_OPENAI_ENDPOINT:
                self.custom_endpoint = settings.AZURE_OPENAI_ENDPOINT
                self.use_direct_http = True
                print(f"LLM Service: Switched to Direct HTTP for {self.custom_endpoint}")
            else:
                self.use_direct_http = False
                # Use Entra ID (Managed Identity or CLI login)
                token_provider = get_bearer_token_provider(
                    DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
                )
                self.client = AsyncAzureOpenAI(
                    azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
                    azure_ad_token_provider=token_provider,
                    api_version=settings.AZURE_OPENAI_API_VERSION,
                    http_client=self.http_client
                )
            self.deployment = settings.AZURE_OPENAI_DEPLOYMENT
            self.is_mock = False
        else:
            self.client = None
            self.is_mock = True

    async def generate_response(self, messages, tools=None):
        print(f"LLM generate_response called. Mock: {self.is_mock}")
        if self.is_mock:
            # Simple mock response
            return FakeMessage({
                "content": "This is a simulated response because Azure OpenAI is not configured.",
                "tool_calls": None
            })
        
        try:
            if getattr(self, 'use_direct_http', False):
                # Direct HTTP Implementation for Custom Gateway
                url = f"{self.custom_endpoint}?api-version={settings.AZURE_OPENAI_API_VERSION}"
                headers = {
                    "api-key": settings.AZURE_OPENAI_API_KEY,
                    "Content-Type": "application/json"
                }
                # Gateway seems to auto-detect model, but we can try sending it if needed.
                # Debug script worked WITHOUT model. Let's send everything except model if possible,
                # or send it and hope it's ignored.
                # Actually, standard OpenAI has 'model', but this gateway might behave differently.
                payload = {
                    "messages": messages,
                    # "model": self.deployment, # Commented out based on debug success
                }
                if tools:
                    payload["tools"] = tools

                print(f"LLM Direct POST: {url}")
                resp = await self.http_client.post(url, json=payload, headers=headers)
                
                if resp.status_code != 200:
                    print(f"LLM Error {resp.status_code}: {resp.text}")
                    return FakeMessage({"content": f"LLM Error {resp.status_code}: {resp.text}", "tool_calls": None})
                
                data = resp.json()
                return FakeMessage(data['choices'][0]['message'])

            # Standard SDK Call
            response = await self.client.chat.completions.create(
                model=self.deployment,
                messages=messages,
                tools=tools
            )
            return response.choices[0].message
        except Exception as e:
            import traceback
            print(f"LLM Exception ({type(e).__name__}): {e}")
            print(f"Traceback: {traceback.format_exc()}")
            return FakeMessage({"content": f"Error calling LLM: {str(e)}", "tool_calls": None})

class FakeMessage:
    def __init__(self, msg_dict):
        self.role = msg_dict.get('role', 'assistant')
        self.content = msg_dict.get('content')
        raw_tool_calls = msg_dict.get('tool_calls')
        self.tool_calls = []
        if raw_tool_calls:
            for tc in raw_tool_calls:
                self.tool_calls.append(FakeToolCall(tc))
        if not self.tool_calls:
            self.tool_calls = None

    def to_dict(self):
        res = {"role": self.role, "content": self.content}
        if self.tool_calls:
            res["tool_calls"] = [tc.to_dict() for tc in self.tool_calls]
        return res

class FakeToolCall:
    def __init__(self, tc_dict):
        self.id = tc_dict.get('id', 'call_abc123')
        self.type = "function"
        self.function = FakeFunction(tc_dict['function'])

    def to_dict(self):
        return {
            "id": self.id,
            "type": self.type,
            "function": self.function.to_dict()
        }

class FakeFunction:
    def __init__(self, fn_dict):
        self.name = fn_dict['name']
        self.arguments = fn_dict['arguments']

    def to_dict(self):
        return {
            "name": self.name,
            "arguments": self.arguments
        }


