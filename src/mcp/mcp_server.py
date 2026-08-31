#!/Users/sethrose/Developer/github/Temp/alexa-mcp/.venv/bin/python
import sys
import os
import logging
import requests  # For making API calls
import json
from typing import List, Dict, Any, Optional, Union
from pathlib import Path

# --- Path Modification ---
# No longer needed as we read API_PORT directly from env
# --- End Path Modification ---

# --- Setup Project Root ---
# REMOVED File Logging Setup
# --- End Setup ---

# Import the local config
try:
    from . import config as mcp_config
    from .alexa_api import ( # Relative import
        get_all_shopping_lists,
        get_shopping_list_items,
        add_shopping_list_item,
        delete_shopping_list_item,
        mark_item_as_completed,
        unmark_item_as_completed,
        filter_incomplete_items,
        # No filter_completed_items, we'll do it inline
    )
except ImportError as e:
    print(f"Error importing local MCP config: {e}", file=sys.stderr)
    print("Ensure you are running from the project root or have activated the correct environment.", file=sys.stderr)
    sys.exit(1)

from fastmcp import FastMCP

# Configure logging based on local config
logging.basicConfig(level=mcp_config.LOG_LEVEL_INT, format='%(asctime)s - %(name)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# --- Add File Handler ---
# Create file handler which logs even debug messages
# REMOVED File Handler Setup
# --- End File Handler Setup ---

# API server configuration
# Use base URL directly from local config
API_BASE_URL = mcp_config.API_BASE_URL

logger.info(f"MCP Server configured to connect to API at: {mcp_config.API_BASE_URL}")

# Suppress noisy library logs based on loaded config
if mcp_config.LOG_LEVEL_INT > logging.DEBUG:
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logger.debug("Suppressed noisy library logs.")

print("--- DEBUG: Initializing FastMCP server...", file=sys.stderr)

# --- FastMCP Server Instance ---
mcp = FastMCP("Alexa Shopping List")

print("--- DEBUG: FastMCP server instance created.", file=sys.stderr)

# --- Helper Functions ---
def make_api_request(method: str, endpoint: str, json_data: Optional[Dict] = None) -> Dict:
    """Makes a request to the FastAPI server and handles errors."""
    url = f"{API_BASE_URL}{endpoint}"
    logger.debug(f"Making {method} request to FastAPI: {url}")

    try:
        if method.upper() == "GET":
            response = requests.get(url)
        elif method.upper() == "POST":
            response = requests.post(url, json=json_data)
        elif method.upper() == "PUT":
            response = requests.put(url, json=json_data)
        elif method.upper() == "DELETE":
            response = requests.delete(url, json=json_data)
        else:
            logger.error(f"Unsupported HTTP method: {method}")
            return {"error": f"Unsupported HTTP method: {method}"}

        # Raise exception for 4xx/5xx status codes
        response.raise_for_status()

        # Try to parse JSON, fall back to text if not JSON
        try:
            return response.json()
        except json.JSONDecodeError:
            return {"message": response.text}

    except requests.exceptions.ConnectionError:
        logger.error(f"Connection error: Could not connect to FastAPI server at {API_BASE_URL}")
        return {"error": "Could not connect to FastAPI server. Is it running?"}
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error: {e}")
        # Try to get error details from the response
        try:
            error_detail = response.json().get("detail", str(e))
        except (json.JSONDecodeError, AttributeError):
            error_detail = str(e)
        return {"error": error_detail}
    except Exception as e:
        logger.error(f"Error making API request: {e}")
        return {"error": str(e)}

# --- Tool Definitions ---
# These now proxy requests to our FastAPI server

@mcp.tool()
def get_lists() -> list[dict]:
    """
    Retrieves the Alexa lists available to the account.
    """
    logger.info("Tool 'get_lists' called.")
    
    lists = get_all_shopping_lists()

    # Make sure we return a list even if API somehow returns something else
    if isinstance(lists, list):
        return lists  # API already returns the list format we need
    else:
        logger.warning(f"Unexpected response format from API, expected list but got: {type(lists)}")
        return []



@mcp.tool()
def get_all_items(list_name: str) -> list[dict]:
    """
    Retrieves all items currently on the Alexa shopping list, including both active (incomplete) and completed items.
    Returns a list of dictionaries, where each dictionary represents an item and includes keys like 'id', 'value', and 'completed'.
    An empty list is returned if the shopping list is empty or an error occurs.
    """
    logger.info(f"Tool 'get_all_items' called with list_name: '{list_name}'.")
    all_items = get_shopping_list_items(list_name)

    # Make sure we return a list even if API somehow returns something else
    if isinstance(all_items, list):
        return all_items  # API already returns the list format we need
    else:
        logger.warning(f"Unexpected response format from API, expected list but got: {type(all_items)}")
        return []

@mcp.tool()
def get_incomplete_items(list_name: str) -> list[dict]:
    """
    Retrieves only the active (incomplete) items currently on the Alexa shopping list.
    This is useful for seeing what still needs to be purchased.
    Returns a list of dictionaries, each representing an item with keys like 'id', 'value', and 'completed' (which will be false).
    An empty list is returned if there are no active items or an error occurs.
    """
    logger.info(f"Tool 'get_incomplete_items' called with list_name: '{list_name}'.")

    all_items = get_shopping_list_items(list_name) # No longer needs config passed
    if all_items is None:
        logger.error("Failed to retrieve items from Alexa API.")
        raise HTTPException(status_code=503, detail="Could not retrieve shopping list from Alexa.")

    incomplete_items = filter_incomplete_items(all_items)

    # Make sure we return a list even if API somehow returns something else
    if isinstance(incomplete_items, list):
        return incomplete_items
    else:
        logger.warning(f"Unexpected response format from API, expected list but got: {type(incomplete_items)}")
        return []

@mcp.tool()
def get_completed_items(list_name: str) -> list[dict]:
    """
    Retrieves only the completed items currently on the Alexa shopping list.
    This shows items that have been marked as done.
    Returns a list of dictionaries, each representing an item with keys like 'id', 'value', and 'completed' (which will be true).
    An empty list is returned if there are no completed items or an error occurs.
    """
    logger.info(f"Tool 'get_completed_items' called with list_name: '{list_name}'.")
    all_items = get_shopping_list_items(list_name) # No longer needs config passed
    if all_items is None:
        logger.error("Failed to retrieve items from Alexa API.")
        raise HTTPException(status_code=503, detail="Could not retrieve shopping list from Alexa.")

    # Filter completed items directly
    completed_items = [item for item in all_items if item.get('completed', False)]

    # Make sure we return a list even if API somehow returns something else
    if isinstance(completed_items, list):
        return completed_items
    else:
        logger.warning(f"Unexpected response format from API, expected list but got: {type(completed_items)}")
        return []

@mcp.tool()
def add_item(item_name: Union[str, List[str]]) -> dict:
    """
    Adds one or more new items to the Alexa shopping list.
    Input can be a single item name as a string (e.g., "Milk") or a list of item names as strings (e.g., ["Eggs", "Bread"]).
    Returns a dictionary indicating the overall success or failure and a summary message.
    If adding multiple items, it attempts to add each one; the overall result is success only if all additions succeed.
    """
    logger.info(f"Tool 'add_item' called with item_name(s): '{item_name}'")

    item_names = [item_name] if isinstance(item_name, str) else item_name
    results = []
    all_succeeded = True

    for name in item_names:
        if not isinstance(name, str) or not name.strip():
             logger.warning(f"Skipping invalid item name: {name}")
             results.append({"item": name, "success": False, "message": "Invalid item name provided."})
             all_succeeded = False
             continue

        response = make_api_request("POST", "/items", {"item_name": name.strip()})
        success = "error" not in response
        message = response.get("message", response.get("error", "Unknown result"))
        results.append({"item": name.strip(), "success": success, "message": message})
        if not success:
            all_succeeded = False
            logger.error(f"Error adding item '{name.strip()}': {message}")

    # Construct summary message
    if len(item_names) == 1:
        summary_message = results[0]['message']
    else:
        success_count = sum(1 for r in results if r['success'])
        fail_count = len(results) - success_count
        if all_succeeded:
            summary_message = f"Successfully added {success_count} items."
        elif success_count > 0:
             summary_message = f"Added {success_count} items, failed to add {fail_count} items. Check logs for details."
        else:
             summary_message = f"Failed to add all {fail_count} items. Check logs for details."

    return {"success": all_succeeded, "message": summary_message, "details": results}

@mcp.tool()
def delete_item(list_name: str, item_name: Union[str, List[str]]) -> dict:
    """
    Deletes one or more items from the specified Alexa shopping list by their exact name (case-insensitive).
    Input can be a single item name as a string (e.g., "Milk") or a list of item names as strings (e.g., ["Old Bread", "Expired Yogurt"]).
    Requires an exact match of the item name to find it on the list. If multiple items have the same name, only one might be deleted per name provided.
    Returns a dictionary indicating the overall success or failure and a summary message.
    If deleting multiple items, it attempts each one; the overall result is success only if all deletions succeed.
    """
    logger.info(f"Tool 'delete_item' called with item_name(s): '{item_name}' for list '{list_name}'")

    item_names = [item_name] if isinstance(item_name, str) else item_name
    results = []
    all_succeeded = True

    all_items = get_shopping_list_items(list_name)
    if all_items is None:
        logger.error(f"Failed to retrieve items from list '{list_name}' for deletion.")
        return {
            "success": False,
            "message": f"Could not retrieve shopping list '{list_name}' from Alexa.",
            "details": [{"item": name, "success": False, "message": "List unavailable."} for name in item_names]
        }

    for name in item_names:
        if not isinstance(name, str) or not name.strip():
             logger.warning(f"Skipping invalid item name for deletion: {name}")
             results.append({"item": name, "success": False, "message": "Invalid item name provided."})
             all_succeeded = False
             continue

        success = delete_shopping_list_item(all_items, name)
        message = "Deleted successfully." if success else "Failed to delete item."
        results.append({"item": name.strip(), "success": success, "message": message})
        if not success:
            all_succeeded = False
            logger.error(f"Error deleting item '{name.strip()}' from list '{list_name}'.")

    # Construct summary message
    if len(item_names) == 1:
        summary_message = results[0]['message']
    else:
        success_count = sum(1 for r in results if r['success'])
        fail_count = len(results) - success_count
        if all_succeeded:
            summary_message = f"Successfully deleted {success_count} items."
        elif success_count > 0:
             summary_message = f"Deleted {success_count} items, failed to delete {fail_count} items (may not exist or error occurred). Check logs."
        else:
             summary_message = f"Failed to delete any of the {fail_count} specified items (may not exist or error occurred). Check logs."

    return {"success": all_succeeded, "message": summary_message, "details": results}

@mcp.tool()
def mark_item_completed(item_name: Union[str, List[str]]) -> dict:
    """
    Marks one or more items on the Alexa shopping list as completed by their exact name (case-insensitive).
    Input can be a single item name as a string (e.g., "Milk") or a list of item names as strings (e.g., ["Eggs", "Bread"]).
    Requires an exact match of the item name to find it on the list. If multiple items have the same name, only one might be marked per name provided.
    Returns a dictionary indicating the overall success or failure and a summary message.
    If marking multiple items, it attempts each one; the overall result is success only if all attempts succeed.
    """
    logger.info(f"Tool 'mark_item_completed' called with item_name(s): '{item_name}'")

    item_names = [item_name] if isinstance(item_name, str) else item_name
    results = []
    all_succeeded = True

    for name in item_names:
        if not isinstance(name, str) or not name.strip():
             logger.warning(f"Skipping invalid item name for completion: {name}")
             results.append({"item": name, "success": False, "message": "Invalid item name provided."})
             all_succeeded = False
             continue

        response = make_api_request("PUT", "/items/mark_completed", {"item_name": name.strip()})
        success = "error" not in response
        message = response.get("message", response.get("error", "Unknown result"))
        results.append({"item": name.strip(), "success": success, "message": message})
        if not success:
            all_succeeded = False
            logger.error(f"Error marking item '{name.strip()}' completed: {message}")

    # Construct summary message
    if len(item_names) == 1:
        summary_message = results[0]['message']
    else:
        success_count = sum(1 for r in results if r['success'])
        fail_count = len(results) - success_count
        if all_succeeded:
            summary_message = f"Successfully marked {success_count} items as completed."
        elif success_count > 0:
             summary_message = f"Marked {success_count} items completed, failed to mark {fail_count} items (may not exist or error occurred). Check logs."
        else:
             summary_message = f"Failed to mark any of the {fail_count} specified items as completed (may not exist or error occurred). Check logs."

    return {"success": all_succeeded, "message": summary_message, "details": results}

@mcp.tool()
def mark_item_incomplete(item_name: Union[str, List[str]]) -> dict:
    """
    Marks one or more previously completed items on the Alexa shopping list as incomplete (active) by their exact name (case-insensitive).
    Input can be a single item name as a string (e.g., "Milk") or a list of item names as strings (e.g., ["Eggs", "Bread"]).
    Requires an exact match of the item name to find it on the list. If multiple items have the same name, only one might be marked per name provided.
    Use this if an item was marked completed by mistake.
    Returns a dictionary indicating the overall success or failure and a summary message.
    If marking multiple items, it attempts each one; the overall result is success only if all attempts succeed.
    """
    logger.info(f"Tool 'mark_item_incomplete' called with item_name(s): '{item_name}'")

    item_names = [item_name] if isinstance(item_name, str) else item_name
    results = []
    all_succeeded = True

    for name in item_names:
        if not isinstance(name, str) or not name.strip():
             logger.warning(f"Skipping invalid item name for marking incomplete: {name}")
             results.append({"item": name, "success": False, "message": "Invalid item name provided."})
             all_succeeded = False
             continue

        response = make_api_request("PUT", "/items/mark_incomplete", {"item_name": name.strip()})
        success = "error" not in response
        message = response.get("message", response.get("error", "Unknown result"))
        results.append({"item": name.strip(), "success": success, "message": message})
        if not success:
            all_succeeded = False
            logger.error(f"Error marking item '{name.strip()}' incomplete: {message}")

     # Construct summary message
    if len(item_names) == 1:
        summary_message = results[0]['message']
    else:
        success_count = sum(1 for r in results if r['success'])
        fail_count = len(results) - success_count
        if all_succeeded:
            summary_message = f"Successfully marked {success_count} items as incomplete."
        elif success_count > 0:
             summary_message = f"Marked {success_count} items incomplete, failed to mark {fail_count} items (may not exist or error occurred). Check logs."
        else:
             summary_message = f"Failed to mark any of the {fail_count} specified items as incomplete (may not exist or error occurred). Check logs."

    return {"success": all_succeeded, "message": summary_message, "details": results}

# --- API Status Check ---
@mcp.tool()
def check_api_status() -> dict:
    """
    Checks if the backend FastAPI server (responsible for communicating with the actual Alexa API) is running and accessible.
    This is useful for diagnosing connection issues between the MCP server and the FastAPI server.
    Returns a dictionary with 'status' ('OK' or 'ERROR') and a descriptive 'message'.
    """
    logger.info("Tool 'check_api_status' called.")
    response = make_api_request("GET", "/")

    if "error" in response:
        logger.error(f"API status check failed: {response['error']}")
        return {
            "status": "ERROR",
            "message": f"FastAPI server is not accessible: {response['error']}"
        }

    return {
        "status": "OK",
        "message": "FastAPI server is running and accessible.",
        "details": response
    }

# --- Run Server ---
if __name__ == "__main__":
    print("--- DEBUG: Entering __main__ block.", file=sys.stderr)
    logger.info("Starting FastMCP server...")
    print("--- MCP Server: Starting ---", file=sys.stderr); sys.stderr.flush()

    # Initial API health check with added error handling
    # --- TEMPORARILY DISABLED Initial API Health Check for Debugging Startup ---
    print("--- MCP Server: Skipping initial API health check... ---", file=sys.stderr); sys.stderr.flush()
    # --- End Disabled Check ---

    try:
        print("--- DEBUG: Calling mcp.run()...", file=sys.stderr)
        print("--- MCP Server: Entering mcp.run() ---", file=sys.stderr); sys.stderr.flush()

        mcp.run(transport="streamable-http", host="localhost", port=4000)

        print("--- DEBUG: mcp.run() completed (or exited).", file=sys.stderr)
    except Exception as e:
        print(f"--- MCP Server FATAL ERROR: Exception from mcp.run(): {e} ---", file=sys.stderr)
        logger.exception(f"Exception from mcp.run(): {e}")  # Log with traceback via logger
        import traceback
        traceback.print_exc(file=sys.stderr)  # Also print traceback directly
        sys.stderr.flush()
        sys.exit(1)  # Ensure exit on error from run
    finally:
        print("--- MCP Server: mcp.run() exited ---", file=sys.stderr); sys.stderr.flush()
        logger.info("FastMCP server finished.")
    print("--- DEBUG: Exiting __main__ block normally.", file=sys.stderr)
