"""Functions for interacting with the Alexa API (shopping list)."""

import json
import logging
import requests
from http.cookies import SimpleCookie
from collections import defaultdict
from typing import Optional, List, Dict, Any

# Import the local config module itself
from . import config as api_config

logger = logging.getLogger(__name__)

# Define headers for requests (Consider making configurable or dynamic)
DEFAULT_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (iPhone; CPU iPhone OS 13_5_1 like Mac OS X)"
                   " AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148"
                   " PitanguiBridge/2.2.345247.0-[HARDWARE=iPhone10_4][SOFTWARE=13.5.1]"),
    "Accept": "*/*",
    "Accept-Language": "*",
    "DNT": "1",
    "Upgrade-Insecure-Requests": "1"
}

# --- Cookie Handling ---

# Hardcoded path for cookie loading *within the container*
# Adjusted for JSON format
CONTAINER_COOKIE_PATH = "/app/data/cookies.json"

def load_cookies_from_json_file(cookie_file_path: str) -> Optional[List[Dict[str, Any]]]:
    """Loads cookies from a JSON file (expected list of dicts)."""
    try:
        with open(cookie_file_path, 'r', encoding='utf-8') as f:
            cookies_list = json.load(f) # Load list of cookie dicts

        if not isinstance(cookies_list, list):
            logger.error(f"Expected a list in {cookie_file_path}, got {type(cookies_list)}.")
            return None

        # Return the full list of dictionaries for detailed processing
        logger.debug(f"Successfully loaded {len(cookies_list)} cookie dicts from JSON: {cookie_file_path}")
        return cookies_list

    except FileNotFoundError:
        logger.error(f"Cookie file not found: {cookie_file_path}")
        return None
    except json.JSONDecodeError as json_err:
        logger.error(f"Failed to decode JSON from {cookie_file_path}: {json_err}")
        return None
    except Exception as err:
        logger.error(f"Failed to load or parse cookies from JSON file {cookie_file_path}: {err}", exc_info=True)
        return None

# --- API Request Function ---
def make_authenticated_request(
    url: str,
    # cookie_file_path: str, # No longer needed as parameter
    method: str = 'GET',
    payload: Optional[Dict[str, Any]] = None
) -> Optional[requests.Response]:
    """Makes an authenticated request using cookies from the fixed container path."""
    try:
        session = requests.Session()
        session.headers.update(DEFAULT_HEADERS)
        # Always load from the container path
        cookie_list_of_dicts = load_cookies_from_json_file(CONTAINER_COOKIE_PATH)

        if not cookie_list_of_dicts:
            logger.error(f"No cookies loaded from {CONTAINER_COOKIE_PATH} for authenticated request.")
            return None

        # Set cookies individually using requests' set method
        for cookie_dict in cookie_list_of_dicts:
            name = cookie_dict.get('name')
            value = cookie_dict.get('value')
            domain = cookie_dict.get('domain')
            path = cookie_dict.get('path')

            if name and value:
                logger.debug(f"Setting cookie: name={name}, domain={domain}, path={path}")
                session.cookies.set(
                    name=name,
                    value=value,
                    domain=domain,
                    path=path
                    # requests automatically handles secure/expires/httpOnly for its context
                    # We mainly need name, value, domain, path for session management
                )
            else:
                logger.warning(f"Skipping cookie dict with missing name/value: {cookie_dict}")

        logger.debug(f"Making {method} request to {url}")
        if method.upper() == 'GET':
            response = session.get(url)
        elif method.upper() == 'PUT':
            logger.debug(f"PUT payload: {payload}")
            response = session.put(url, json=payload)
        elif method.upper() == 'POST':
            logger.debug(f"POST payload: {payload}")
            response = session.post(url, json=payload)
        elif method.upper() == 'DELETE':
            logger.debug(f"DELETE request to {url}")
            # Allow DELETE with an optional payload (needed for Alexa API)
            response = session.delete(url, json=payload)
        else:
            logger.error(f"Unsupported method specified: {method}")
            return None

        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        logger.debug(f"Request successful ({response.status_code})")
        return response

    except requests.exceptions.RequestException as err:
        logger.error(f"HTTP request failed: {err}")
        return None
    except Exception as e:
        logger.exception(f"Unexpected error during authenticated request: {e}")
        return None

