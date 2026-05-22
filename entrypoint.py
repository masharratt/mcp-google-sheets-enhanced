from fastapi import FastAPI
import uvicorn
import threading
import sys
import os
import base64
import json

# Import the MCP server
sys.path.insert(0, '/app')
import server

app = FastAPI()

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "mcp-google-sheets-enhanced",
        "version": "1.0.0"
    }

def setup_credentials():
    """Setup Google credentials from environment variable"""
    credentials_config = os.getenv('CREDENTIALS_CONFIG')
    if credentials_config:
        try:
            # Decode base64 credentials
            decoded = base64.b64decode(credentials_config).decode('utf-8')
            creds_data = json.loads(decoded)

            # Write to credentials file
            creds_path = '/app/credentials.json'
            with open(creds_path, 'w') as f:
                json.dump(creds_data, f)

            # Set environment variable for Google SDK
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = creds_path
            print(f"Credentials configured successfully for project: {creds_data.get('project_id')}")
        except Exception as e:
            print(f"Error setting up credentials: {e}")
            raise
    else:
        print("WARNING: CREDENTIALS_CONFIG not found in environment")

def run_health_server():
    """Run health check server on port 8001"""
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="warning")

def run_mcp_server():
    """Run MCP server with SSE transport on port 8000"""
    # Setup credentials before starting MCP server
    setup_credentials()

    # Run MCP server with SSE transport
    print("Starting MCP server with SSE transport on port 8000...")
    sys.argv = ["server.py", "--transport", "sse", "--port", "8000"]

    try:
        server.main()
    except Exception as e:
        print(f"Error running MCP server: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    # Start health server in background thread
    health_thread = threading.Thread(target=run_health_server, daemon=True)
    health_thread.start()

    print("Health server started on port 8001")

    # Run MCP server in main thread
    run_mcp_server()
