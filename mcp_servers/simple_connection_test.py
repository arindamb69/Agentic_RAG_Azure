import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv(dotenv_path="../backend/.env")

url = os.getenv("CONFLUENCE_URL")
subscription_key = os.getenv("CONFLUENCE_SUBSCRIPTION_KEY")

print(f"Testing URL: {url}")
print(f"Subscription Key provided: {'Yes' if subscription_key else 'No'}")

headers = {
    "Ocp-Apim-Subscription-Key": subscription_key,
    "Cache-Control": "no-cache",
    "Accept": "application/json, text/event-stream",
    "Content-Type": "application/json"
}

# Construct a valid MCP initialize request
payload = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2024-11-05", # Use a recent version or 0.1.0
        "capabilities": {
            "roots": {"listChanged": False},
            "sampling": {}
        },
        "clientInfo": {
            "name": "test-client",
            "version": "1.0"
        }
    }
}

print(f"\n--- Testing POST with 'initialize' ---")
try:
    response = requests.post(url, headers=headers, json=payload, timeout=10)
    print(f"Status: {response.status_code}")
    print("Response Headers:")
    for k, v in response.headers.items():
        print(f"  {k}: {v}")
    
    print("\nBody:")
    try:
        data = response.json()
        print(json.dumps(data, indent=2))
        
        # If successful, try to list tools next?
        if "result" in data:
            print("\nInitialization successful! Attempting to list tools...")
            
            # Send initialized notification
            requests.post(url, headers=headers, json={
                "jsonrpc": "2.0",
                "method": "notifications/initialized"
            })

            # List tools
            tools_payload = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list"
            }
            tools_resp = requests.post(url, headers=headers, json=tools_payload, timeout=10)
            print("\nTools Response:")
            print(json.dumps(tools_resp.json(), indent=2))

    except Exception as e:
        print(f"Response (Text): {response.text}")

except Exception as e:
    print(f"Error: {e}")



