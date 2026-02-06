import sys
import os
# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.getcwd(), "..")))

print("Attempting import...")
try:
    from mcp_servers.mcp_confluence import search_wiki
    print("Import successful!")
except Exception as e:
    print(f"Import failed: {e}")
    import traceback
    traceback.print_exc()
