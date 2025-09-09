#!/usr/bin/env python3
"""Start the FastAPI server for the Cloud Storage Transfer Service"""

import os
import sys
import uvicorn
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add src to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.api.main import app

if __name__ == "__main__":
    # Get configuration from environment
    port = int(os.getenv("PORT", "8080"))
    host = os.getenv("HOST", "0.0.0.0")
    reload = os.getenv("RELOAD", "false").lower() == "true"
    
    print(f"Starting Cloud Storage Transfer Service API")
    print(f"Server running at http://{host}:{port}")
    print(f"Documentation available at http://{host}:{port}/docs")
    print(f"OpenAPI spec at http://{host}:{port}/openapi.json")
    
    # Run the server
    uvicorn.run(
        "src.api.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info"
    )