"""Script to force login/re-login, generate the Alexa cookie file, and send it to the API container."""

import logging
import sys
import asyncio
import os
from pathlib import Path
import requests  # Needed for POSTing cookies
from typing import List, Dict, Optional, Union # For cookie formatting type hint
import nodriver as uc
import json # To save cookies locally
import datetime
from pydantic import BaseModel  # For request body validation

try:
    # Import the local auth config
    from . import config as auth_config
except ImportError as e:
    print(f"Error importing local config: {e}", file=sys.stderr)
    print("Ensure you are running from the project root or have activated the correct environment.", file=sys.stderr)
    sys.exit(1)

# --- Path Modification ---
# Add the project root directory to the Python path
# This allows importing modules from the 'src' directory (e.g., alexa_shopping_list)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.append(project_root)
# --- End Path Modification ---

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

async def receive_cookies(cookies_data: List[CookieModel]): # Expect a list of CookieModel
    """Saves cookies to the JSON file the MCP server reads from."""
    # COOKIE_PATH is relative to the project root, same as src/mcp/config.py's COOKIE_PATH
    cookie_path = os.path.join(project_root, auth_config.COOKIE_PATH)
    data_dir_container = os.path.dirname(cookie_path) # Get directory from the path

    logger.info(f"Received {len(cookies_data)} cookies. Attempting to save as JSON to: {cookie_path}")

    # Create directory if it doesn't exist
    try:
        os.makedirs(data_dir_container, exist_ok=True)
    except OSError as e:
        logger.error(f"Could not create data directory '{data_dir_container}': {e}", exc_info=True)
        raise RuntimeError("Server error: Could not create data directory.")

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
        raise RuntimeError(f"Failed to save cookie data: {e}")



logger = logging.getLogger("login_script")  # Renamed logger for clarity

# Constructing URL based on signIn.js structure but with our return_to target
direct_signin_url = "https://www.amazon.com/"

async def post_cookies_to_api(cookies_for_requests: List[Dict]):
    """Posts the cookies (in requests format) to the API endpoint as JSON."""
    # Post to API
    logger.info(f"Attempting to send cookies as JSON to API endpoint: {auth_config.API_COOKIE_ENDPOINT}")
    try:
        # Send the list of cookie dictionaries as JSON
        response = requests.post(auth_config.API_COOKIE_ENDPOINT, json=cookies_for_requests, timeout=15)
        response.raise_for_status()
        logger.info(f"Successfully sent cookies to API. Status: {response.status_code}")
        return True
    except requests.exceptions.ConnectionError as conn_err:
        logger.error(f"Could not connect to the API server at {auth_config.API_COOKIE_ENDPOINT}. Is it running?")
        logger.error(f"Error: {conn_err}")
    except requests.exceptions.Timeout:
        logger.error(f"Timeout while sending cookie file to {auth_config.API_COOKIE_ENDPOINT}.")
    except requests.exceptions.RequestException as req_err:
        logger.error(f"Error sending cookie file to API: {req_err}")
        if req_err.response is not None:
            logger.error(f"API Response Status: {req_err.response.status_code}")
            logger.error(f"API Response Body: {req_err.response.text}")
    except Exception as upload_err:
        logger.error(f"Unexpected error during cookie file upload: {upload_err}", exc_info=True)
    return False

async def main():
    """Opens browser to sign-in page, waits for manual login, then extracts cookies."""
    logging.basicConfig(
        level=auth_config.LOG_LEVEL_INT,
        format='%(asctime)s - %(name)s [%(levelname)s] %(message)s',
        stream=sys.stdout
    )

    logger.info("Starting Alexa authentication process with nodriver...")

    browser = None
    page = None

    # Flag for final outcome
    cookie_upload_success = False

    try:
        # --- Step 1: Open Browser to Sign-in Page --- #
        logger.info("Initializing nodriver browser...")
        browser = await uc.start() # Headless by default
        page = await browser.get(direct_signin_url)
        logger.info(f"Navigated directly to: {direct_signin_url}")

        # --- Step 2: Wait for Manual Login --- #
        print("-" * 60)
        print("*** MANUAL LOGIN REQUIRED ***")
        print("A browser window should have opened to the Amazon sign-in page.")
        print("Please log in manually within that browser window.")
        print("If you encounter 2FA or CAPTCHA, complete those steps in the browser.")
        input("--> Press Enter here AFTER you have successfully logged in... ")
        print("-" * 60)
        logger.info("User indicated manual login complete. Attempting to extract cookies.")

        # --- Step 5: Extract and Post Cookies ---
        # Always attempt cookie extraction after verification steps or manual intervention pause
        # The login_success flag now only indicates if the *automated* part seemed to succeed.
        # The login_and_upload_success flag tracks the actual cookie extraction/upload result.
        logger.info("Proceeding to Step 5: Extract and Post Cookies attempt...")

        # --- Start Cookie Extraction Logic --- #
        logger.info("Attempting to extract cookies...")
        # Use the documented way to get all cookies for the current context/page
        # Access cookies through the browser object, not the page/tab object
        raw_cookies = await browser.cookies.get_all(requests_cookie_format=True)

        if not raw_cookies:
            logger.error("Failed to extract cookies after manual login attempt.")
            # Add a re-check here based on greeting if possible (might be useful even after manual intervention)
            try:
                final_greeting = await page.evaluate('''() => {
                    const el = document.querySelector('#nav-link-accountList .nav-line-1');
                    return el ? el.innerText.trim() : null;
                }''')
                if not (final_greeting and "Hello," in final_greeting):
                    logger.error("Double-check: Still not logged in according to greeting element, despite manual confirmation.")
                # No need for specific log if cookies extraction failed BUT login_success was True and greeting was found
            except Exception:
                logger.warning("Could not perform final greeting check.")
            # login_and_upload_success remains False
        else:
            logger.info(f"Successfully extracted {len(raw_cookies)} raw cookie objects.")

            # Convert Cookie objects to JSON serializable list of dicts
            serializable_cookies = []
            for cookie in raw_cookies:
                # Extract common attributes, handle potential None values
                cookie_dict = {
                    "name": getattr(cookie, 'name', None),
                    "value": getattr(cookie, 'value', None),
                    "domain": getattr(cookie, 'domain', None),
                    "path": getattr(cookie, 'path', None),
                    "expires": getattr(cookie, 'expires', None), # May need conversion if not serializable
                    "secure": getattr(cookie, 'secure', False),
                    "httpOnly": getattr(cookie, 'httpOnly', False), # Try direct access
                    # Add other relevant fields if needed, e.g., sameSite
                }
                # Filter out None values if necessary, or handle expires conversion
                serializable_cookies.append({k: v for k, v in cookie_dict.items() if v is not None})

            logger.info(f"Formatted {len(serializable_cookies)} cookies for JSON.")
            # Call receive_cookies directly instead of POSTing to the API server that used to call it
            try:
                await receive_cookies([CookieModel(**c) for c in serializable_cookies])
                cookie_upload_success = True
                logger.info("Manual login confirmation received and cookies sent successfully.")
            except Exception as e:
                cookie_upload_success = False
                logger.error(f"Cookie extraction may have succeeded, but saving cookies failed: {e}")
        # --- End Cookie Extraction Logic --- #

        if not cookie_upload_success:
             logger.error("Overall process failed (cookie extraction or upload failed). Exiting with error status.")
             sys.exit(1)
        else:
            logger.info("Process completed successfully.")

    except Exception as e:
        # Catch top-level errors in the main login flow
        logger.exception(f"An unexpected error occurred during the nodriver login process: {e}")
        if page:
            try:
                # Save final page state on uncaught exception - REMOVED
                pass
            except Exception as screenshot_err:
                logger.warning(f"Could not save error screenshot: {screenshot_err}")
        sys.exit(1)
    finally:
        if browser:
            logger.info("Closing nodriver browser...")
            try:
                browser.stop() # Use stop() to close nodriver browser (synchronous)
                logger.info("Browser closed.")
            except Exception as close_err:
                 logger.warning(f"Error closing browser: {close_err}")

if __name__ == "__main__":
    try:
        uc.loop().run_until_complete(main())
    except KeyboardInterrupt:
        logging.getLogger().info("Login process interrupted by user.")
        sys.exit(0)
    except Exception as main_err:
         # Catch errors happening outside the main async function itself
         logging.getLogger().exception(f"Critical error running main: {main_err}")
         sys.exit(1)
