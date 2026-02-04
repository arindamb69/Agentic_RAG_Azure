from mcp.server.fastmcp import FastMCP
import httpx

# Stub for Architecture Diagram Generator
mcp = FastMCP("ArchitectureDesigner")

@mcp.tool()
async def generate_diagram(description: str, diagram_type: str = "mermaid") -> str:
    """
    Generates an architecture diagram based on the description.
    Supported types: 'mermaid', 'c4', 'plantuml'.
    Returns the code for the diagram.
    """
    
    if diagram_type.lower() == "mermaid":
        return f"""
graph TD
    User[User] -->|HTTPS| Frontend[React App]
    Frontend -->|API| Backend[FastAPI Backend]
    Backend -->|Orchestrates| Agent[AI Agent]
    Agent -->|Uses| Tools[MCP Tools]
    Tools -->|Queries| DB[(Azure SQL)]
    Tools -->|Search| Search[(Azure AI Search)]
    
    subgraph "Generated from: {description[:20]}..."
    end
"""
    elif diagram_type.lower() == "c4":
         return f"""
C4Context
    title "System Context Diagram for {description[:20]}..."
    Person(user, "User", "A user of the system")
    System(system, "Software System", "Allows users to {description[:20]}...")
    Rel(user, system, "Uses")
"""
    
    return "Error: Unsupported diagram type. Use 'mermaid' or 'c4'."

if __name__ == "__main__":
    mcp.run()
