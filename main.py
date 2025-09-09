#!/usr/bin/env python3
"""Main entry point for the Cloud Storage Transfer Service"""

import sys
import logging
from dotenv import load_dotenv
from src.cli import cli

# Load environment variables from .env file
load_dotenv()

# Configure root logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

if __name__ == '__main__':
    try:
        cli(obj={})
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        sys.exit(1)