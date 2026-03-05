from mcp.server.fastmcp import FastMCP
import httpx
import os
import base64
import json
from dotenv import load_dotenv
from openai import AzureOpenAI

# Load environment variables from backend/.env if available, or .env
# Try to find .env in parent directories
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_env_path = os.path.join(current_dir, "..", "backend", ".env")
if os.path.exists(backend_env_path):
    load_dotenv(backend_env_path)
else:
    load_dotenv()

mcp = FastMCP("ArchitectureDesigner")

def get_llm_client():
    """Initializes and returns the AzureOpenAI client."""
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")

    if not api_key or not azure_endpoint:
        raise ValueError("AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT must be set in .env")

    return AzureOpenAI(
        api_key=api_key,
        api_version=api_version,
        azure_endpoint=azure_endpoint
    )

def generate_mermaid_code(client, deployment, description):
    """Generates Mermaid diagram code using LLM."""
    system_prompt = """You are an expert software architect and Mermaid.js specialist.
    Generate a valid, visually clear Mermaid.js diagram.
    - Use 'flowchart TD' or 'graph TD' for architectural flows, 'sequenceDiagram' for interactions.
    - CRITICAL: EVERY node label MUST be wrapped in double quotes. 
      Correct: A["User Interface"]
      Incorrect: A[User Interface]
    - CRITICAL: For subgraphs, you MUST use the syntax: subgraph ID [Label] (NO QUOTES for subgraph labels!)
      Correct: subgraph CH [Sales Channels]
      Incorrect: subgraph CH ["Sales Channels"]
      Incorrect: subgraph CH[Sales Channels]
      Incorrect: subgraph Sales Channels
    - CRITICAL: labels MUST NOT contain newlines.
    - Use descriptive names for nodes.
    - Return ONLY the code block, NO markdown backticks or explanations."""
    
    response = client.chat.completions.create(
        model=deployment,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Create a detailed Mermaid diagram for: {description}"}
        ],
        temperature=0.1
    )
    return response.choices[0].message.content.strip()

def generate_c4_code(client, deployment, description):
    """Generates C4-PlantUML diagram code using LLM."""
    system_prompt = """You are an expert software architect and C4 model specialist.
    Generate a C4 Context or Container diagram using C4-PlantUML syntax.
    - Use '!include https://raw.githubusercontent.com/plantuml-stdlib/C4-PlantUML/master/C4_Container.puml'
    - Use 'Person()', 'System()', 'Container()', and 'Rel()' macros correctly.
    - IMPORTANT: Return ONLY the PlantUML code, NO markdown backticks or explanations.
    - Start with @startuml and end with @enduml."""

    response = client.chat.completions.create(
        model=deployment,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Create a C4 Context diagram for: {description}"}
        ],
        temperature=0.1
    )
    return response.choices[0].message.content.strip()

def get_mermaid_ink_url(mermaid_code):
    """Generates a mermaid.ink URL for the given Mermaid code."""
    # mermaid.ink requires base64 encoding of the state object
    # Format: https://mermaid.ink/img/<base64_string>
    # The base64 string is simply the standard base64 encoding of the code structure
    # Actually, simpler method: just base64 encode the code itself for mermaid.ink/img/
    # According to mermaid.ink docs: pako deflate + base64url is best, but standard base64 often works for simple cases.
    # Let's use the simple ascii base64 first.
    
    encoded_string = base64.b64encode(mermaid_code.encode("utf-8")).decode("utf-8")
    return f"https://mermaid.ink/img/{encoded_string}"

@mcp.tool()
async def generate_diagram(description: str, diagram_type: str = "mermaid") -> str:
    """
    Generates an architecture diagram based on the description.
    
    Args:
        description: Description of the system to design.
        diagram_type: 'mermaid' or 'c4'.
    """
    try:
        client = get_llm_client()
        deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")

        if diagram_type.lower() == "mermaid":
            code = generate_mermaid_code(client, deployment, description)
            # Robust cleanup
            code = code.replace("```mermaid", "").replace("```", "").strip()
            # If the LLM still prefix with 'mermaid' keyword outside the TD/etc
            if code.lower().startswith("mermaid"):
                code = code[7:].strip()
            
            if not code: return "Error: Could not generate valid Mermaid code."
            return code

        elif diagram_type.lower() == "c4":
            code = generate_c4_code(client, deployment, description)
            code = code.replace("```plantuml", "").replace("```puml", "").replace("```", "").strip()
            if not code: return "Error: Could not generate valid PlantUML code."
            return code
        
        else:
            return f"Error: Unsupported diagram_type '{diagram_type}'."

    except Exception as e:
        return f"Error generating diagram: {str(e)}"

if __name__ == "__main__":
    mcp.run()
