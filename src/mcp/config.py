# Configuration for the MCP Server
import logging

import os
from dataclasses import dataclass
from typing import Optional
import sys

# Logging level for the MCP server
LOG_LEVEL = "INFO"


# Configuration for the API Server (inside Docker)
COOKIE_PATH = "Cookies/cookies.json"

# Amazon URL for your locale (e.g., amazon.com, amazon.co.uk)
# Needs to match the one used for login to construct API paths correctly.
AMAZON_URL = "https://www.amazon.com"

# Host and Port where the API container is running
# Assumes API container is accessible on localhost from where MCP server runs
API_HOST = "localhost"
API_PORT = 8000

# --- Derived --- #
LOG_LEVEL_INT = getattr(logging, LOG_LEVEL.upper(), logging.INFO)
API_BASE_URL = f"http://{API_HOST}:{API_PORT}"
