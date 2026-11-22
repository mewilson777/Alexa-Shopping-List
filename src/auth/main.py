import sys
import os
import logging
from typing import List, Optional, Union
import json # Added json for saving cookies

# --- Path Modification ---
# Add the project root directory to the Python path
# This allows importing modules from the 'src' directory (e.g., alexa_shopping_list)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.append(project_root)
# --- End Path Modification ---

from fastapi import HTTPException
from pydantic import BaseModel  # For request body validation



# Define a Pydantic model for the expected cookie structure (adjust if needed)
class CookieModel(BaseModel):
    name: str
    value: str
    domain: Optional[str] = None
    path: Optional[str] = None
    # Add missing fields based on what login.py sends
    expires: Optional[Union[str, int, float]] = None # Allow various types for expiry
    secure: Optional[bool] = None
    httpOnly: Optional[bool] = None
    # sameSite: Optional[str] = None # Could add if needed

# --- API Endpoints ---


# --- Authentication Endpoint ---
async def receive_cookies(cookies_data: List[CookieModel]): # Expect a list of CookieModel
    """Accepts cookies as JSON and saves them to the persistent data volume."""
    # Use the COOKIE_PATH directly from the local API config
    cookie_path = api_config.COOKIE_PATH
    data_dir_container = os.path.dirname(cookie_path) # Get directory from the path

    logger.info(f"Received {len(cookies_data)} cookies. Attempting to save as JSON to: {cookie_path}")

    # Create directory if it doesn't exist
    try:
        os.makedirs(data_dir_container, exist_ok=True)
    except OSError as e:
        logger.error(f"Could not create data directory '{data_dir_container}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Server error: Could not create data directory.")

    try:
        # Convert Pydantic models back to dicts for JSON serialization
        cookies_list_of_dicts = [cookie.model_dump(exclude_unset=True) for cookie in cookies_data]

        # Save the received cookie list as a JSON file
        with open(cookie_path, "w", encoding="utf-8") as f:
            json.dump(cookies_list_of_dicts, f, indent=2)

        logger.info(f"Successfully saved cookie data as JSON to {cookie_path}")
        return {"message": "Cookie data received and saved successfully."}

    except Exception as e:
        logger.error(f"Failed to save cookie data as JSON to {cookie_path}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to save cookie data: {e}")

