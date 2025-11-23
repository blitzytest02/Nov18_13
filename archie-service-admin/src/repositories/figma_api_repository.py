"""
Figma API Repository Implementation.

This module provides the concrete implementation of IFigmaAPIRepository interface,
handling all external HTTP communications with Figma's REST API. It implements
Personal Access Token validation, frame URL accessibility verification, and
frame metadata retrieval operations.

The repository uses the requests library for HTTP operations and implements
comprehensive error handling for various Figma API failure scenarios including
authentication errors (401), permission errors (403), not found errors (404),
rate limiting (429), and network connectivity issues.

Key Features:
    - PAT validation using Figma's /v1/me endpoint
    - Frame access verification with metadata extraction
    - URL parsing for file keys and node IDs
    - Bearer token authentication
    - HTTP error handling and graceful degradation
    - Structured logging for debugging

Authentication Pattern:
    All requests include Authorization header with Bearer token:
        Authorization: Bearer {pat}

URL Parsing:
    Supports both Figma URL formats:
        - https://www.figma.com/file/{file_key}/...?node-id={node_id}
        - https://www.figma.com/design/{file_key}/...?node-id={node_id}

Error Handling Strategy:
    - PAT validation returns False on any error (never raises)
    - Frame validation returns structured error dict (never raises)
    - Metadata retrieval returns None on any error (never raises)
    - All errors are logged with appropriate context

Implementation Notes:
    - Uses 10-second timeout for PAT validation
    - Uses 15-second timeout for frame operations
    - No retry logic in this layer (can be added by service layer if needed)
    - Thread-safe (no instance state maintained)
"""

import logging
import re
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlparse

import requests
from requests.exceptions import HTTPError, RequestException, Timeout

from .interfaces.i_figma_api_repository import IFigmaAPIRepository

# Module logger for tracking API operations and errors
logger = logging.getLogger(__name__)

# Figma API base URL
FIGMA_API_BASE = "https://api.figma.com/v1"

# Timeout constants (in seconds)
PAT_VALIDATION_TIMEOUT = 10
FRAME_OPERATION_TIMEOUT = 15

# Regex patterns for parsing Figma URLs
# Matches: https://www.figma.com/file/{file_key}/... or .../design/{file_key}/...
FIGMA_URL_PATTERN = re.compile(
    r'https://(?:www\.)?figma\.com/(?:file|design)/([a-zA-Z0-9]+)(?:/[^?]*)?'
)


class FigmaAPIRepository(IFigmaAPIRepository):
    """
    Production implementation of IFigmaAPIRepository for Figma REST API operations.

    This repository handles all external HTTP communications with Figma's API,
    providing methods for PAT validation, frame access verification, and metadata
    retrieval. It implements proper error handling, authentication, and logging
    to ensure reliable integration with Figma's services.

    The implementation follows the repository pattern per requirement B.1, isolating
    external API dependencies and enabling the service layer to interact with Figma
    without knowledge of HTTP client details or API specifics.

    Thread Safety:
        This class is thread-safe as it maintains no instance state. Each method
        operates independently with parameters provided by the caller.

    Usage Example:
        >>> api_repo = FigmaAPIRepository()
        >>> is_valid = api_repo.validate_pat("figd_AbC123...")
        >>> if is_valid:
        ...     result = api_repo.validate_frame_access(
        ...         "figd_AbC123...",
        ...         "https://www.figma.com/file/abc/design?node-id=1:2"
        ...     )
        ...     if result['valid']:
        ...         print(f"Frame title: {result['title']}")
    """

    def __init__(self) -> None:
        """
        Initialize the Figma API repository.

        No configuration or state is stored at the instance level. All necessary
        parameters (PAT, URLs) are provided through method calls, making this
        class stateless and thread-safe.
        """
        logger.debug("FigmaAPIRepository initialized")

    def validate_pat(self, pat: str) -> bool:
        """
        Validate Personal Access Token by making a test API call to Figma.

        Makes a lightweight request to Figma's /v1/me endpoint to verify the PAT
        is valid and active. This method is used to compute the PAT status
        (Active/Expired) for installation records per requirement A.4.

        The validation uses the /v1/me endpoint which returns basic user information
        if the PAT is valid. A successful 200 response indicates the token is active
        and has API access. Any error response or network failure indicates the
        token should be considered invalid or expired.

        :param pat: Figma Personal Access Token to validate
        :type pat: str
        :return: True if PAT is valid and active, False if invalid, expired, or any error occurs
        :rtype: bool

        HTTP Status Code Handling:
            - 200 OK: PAT is valid → returns True
            - 401 Unauthorized: Invalid or expired PAT → returns False
            - 403 Forbidden: Revoked token → returns False
            - 404 Not Found: Incorrect endpoint (shouldn't happen) → returns False
            - 429 Too Many Requests: Rate limited → returns False
            - 5xx Server Error: Figma API issue → returns False
            - Network timeout: Connection issue → returns False

        Error Handling Philosophy:
            This method NEVER raises exceptions. All error conditions result in
            False return value. This design choice simplifies service layer logic
            by eliminating the need for try-except blocks when checking PAT status.

        Implementation Details:
            - Endpoint: GET https://api.figma.com/v1/me
            - Authentication: Bearer token in Authorization header
            - Timeout: 10 seconds
            - No retry logic (fast fail for status checks)
            - All errors logged for debugging

        Example Usage:
            >>> api_repo = FigmaAPIRepository()
            >>> if api_repo.validate_pat("figd_valid_token"):
            ...     print("PAT is active")
            ... else:
            ...     print("PAT is expired or invalid")
        """
        if not pat or not isinstance(pat, str) or not pat.strip():
            logger.warning("validate_pat called with empty or invalid PAT")
            return False

        try:
            url = f"{FIGMA_API_BASE}/me"
            headers = {
                "Authorization": f"Bearer {pat}",
                "Content-Type": "application/json"
            }

            logger.debug(f"Validating PAT by calling {url}")

            response = requests.get(
                url,
                headers=headers,
                timeout=PAT_VALIDATION_TIMEOUT
            )

            # Check if response is successful (200 OK)
            if response.status_code == 200:
                logger.info("PAT validation successful")
                return True

            # Log specific HTTP error codes for debugging
            if response.status_code == 401:
                logger.warning("PAT validation failed: 401 Unauthorized (invalid or expired token)")
            elif response.status_code == 403:
                logger.warning("PAT validation failed: 403 Forbidden (revoked token)")
            elif response.status_code == 429:
                logger.warning("PAT validation failed: 429 Rate limit exceeded")
            else:
                logger.warning(f"PAT validation failed: HTTP {response.status_code}")

            return False

        except Timeout:
            logger.error(f"PAT validation timeout after {PAT_VALIDATION_TIMEOUT} seconds")
            return False

        except RequestException as e:
            logger.error(f"PAT validation network error: {e}")
            return False

        except Exception as e:
            # Catch any unexpected errors to ensure we never raise
            logger.error(f"PAT validation unexpected error: {e}", exc_info=True)
            return False

    def validate_frame_access(self, pat: str, frame_url: str) -> Dict[str, Any]:
        """
        Validate PAT has access to frame and retrieve frame metadata.

        Checks if the provided PAT can successfully access the Figma frame specified
        by frame_url. This method is essential for the frame attachment validation
        flow per requirement A.7.1.1, where frame URLs must be validated before
        being stored in the database.

        The method extracts the file key and node ID from the frame_url, makes a
        request to Figma's API to retrieve the frame/node, and returns validation
        status along with the frame title if successful.

        :param pat: Figma Personal Access Token for authentication
        :type pat: str
        :param frame_url: Full Figma frame URL to validate
                         Format: https://www.figma.com/file/{file_key}/{file_name}?node-id={node_id}
                         or: https://www.figma.com/design/{file_key}/{file_name}?node-id={node_id}
        :type frame_url: str
        :return: Dictionary with validation results containing:
                 - valid (bool): True if PAT can access frame, False otherwise
                 - title (str): Frame name/title from Figma API if valid, empty string if invalid
                 - message (str): Error message if validation failed, empty string if successful
        :rtype: Dict[str, Any]

        Return Value Structure:
            Success case:
                {
                    "valid": True,
                    "title": "Login Screen - Mobile",
                    "message": ""
                }

            Error cases always include descriptive message:
                {
                    "valid": False,
                    "title": "",
                    "message": "Invalid Figma frame URL format"
                }

        HTTP Status Code Handling:
            - 200 OK: Frame accessible → returns valid=True with title
            - 401 Unauthorized: Invalid PAT → returns error message about token
            - 403 Forbidden: No access to file → returns access denied message
            - 404 Not Found: Frame doesn't exist → returns not found message
            - 429 Rate Limited: Too many requests → returns rate limit message
            - Network errors: Connection issues → returns network error message

        URL Parsing:
            Supports both URL formats:
                - https://www.figma.com/file/{file_key}/...?node-id={node_id}
                - https://www.figma.com/design/{file_key}/...?node-id={node_id}

            Node ID format variations:
                - Simple: node-id=1:2
                - Encoded: node-id=1%3A2
                Both are handled correctly by URL parsing

        Implementation Details:
            - Endpoint: GET https://api.figma.com/v1/files/{file_key}/nodes?ids={node_id}
            - Authentication: Bearer token in Authorization header
            - Timeout: 15 seconds
            - Response parsing: Extract name from nodes[node_id]['document']['name']
            - Never raises exceptions - returns error dict instead

        Example Usage:
            >>> api_repo = FigmaAPIRepository()
            >>> result = api_repo.validate_frame_access(
            ...     "figd_AbC123...",
            ...     "https://www.figma.com/file/abc/design?node-id=1:2"
            ... )
            >>> if result['valid']:
            ...     print(f"Frame title: {result['title']}")
            ... else:
            ...     print(f"Validation failed: {result['message']}")
        """
        # Validate inputs
        if not pat or not isinstance(pat, str) or not pat.strip():
            logger.warning("validate_frame_access called with empty or invalid PAT")
            return {
                "valid": False,
                "title": "",
                "message": "Personal Access Token is required"
            }

        if not frame_url or not isinstance(frame_url, str) or not frame_url.strip():
            logger.warning("validate_frame_access called with empty or invalid frame_url")
            return {
                "valid": False,
                "title": "",
                "message": "Frame URL is required"
            }

        # Parse the Figma URL to extract file_key and node_id
        parsed_data = self._parse_figma_url(frame_url)
        if not parsed_data:
            logger.warning(f"Invalid Figma URL format: {frame_url}")
            return {
                "valid": False,
                "title": "",
                "message": "Invalid Figma frame URL format"
            }

        file_key = parsed_data['file_key']
        node_id = parsed_data['node_id']

        try:
            # Construct Figma API endpoint for node retrieval
            url = f"{FIGMA_API_BASE}/files/{file_key}/nodes"
            headers = {
                "Authorization": f"Bearer {pat}",
                "Content-Type": "application/json"
            }
            params = {
                "ids": node_id
            }

            logger.debug(f"Validating frame access: file_key={file_key}, node_id={node_id}")

            response = requests.get(
                url,
                headers=headers,
                params=params,
                timeout=FRAME_OPERATION_TIMEOUT
            )

            # Handle successful response
            if response.status_code == 200:
                try:
                    data = response.json()

                    # Navigate to the frame/node data in the response
                    # Expected structure: {"nodes": {"{node_id}": {"document": {"name": "..."}}}}
                    if 'nodes' in data and node_id in data['nodes']:
                        node_data = data['nodes'][node_id]

                        # Check if the node was successfully retrieved
                        if node_data is None:
                            logger.warning(f"Node {node_id} not found in file {file_key}")
                            return {
                                "valid": False,
                                "title": "",
                                "message": "Frame not found in the specified file"
                            }

                        # Extract the frame name/title
                        if 'document' in node_data and 'name' in node_data['document']:
                            frame_title = node_data['document']['name']
                            logger.info(f"Frame access validated successfully: {frame_title}")
                            return {
                                "valid": True,
                                "title": frame_title,
                                "message": ""
                            }
                        else:
                            logger.warning(f"Unexpected response structure from Figma API: missing document.name")
                            return {
                                "valid": False,
                                "title": "",
                                "message": "Could not retrieve frame information"
                            }
                    else:
                        logger.warning(f"Node {node_id} not found in response")
                        return {
                            "valid": False,
                            "title": "",
                            "message": "Frame not found or inaccessible"
                        }

                except ValueError as e:
                    logger.error(f"Failed to parse Figma API JSON response: {e}")
                    return {
                        "valid": False,
                        "title": "",
                        "message": "Invalid response from Figma API"
                    }

            # Handle HTTP error responses
            elif response.status_code == 401:
                logger.warning("Frame access validation failed: 401 Unauthorized")
                return {
                    "valid": False,
                    "title": "",
                    "message": "Invalid or expired Personal Access Token"
                }

            elif response.status_code == 403:
                logger.warning("Frame access validation failed: 403 Forbidden")
                return {
                    "valid": False,
                    "title": "",
                    "message": "Access denied to this file"
                }

            elif response.status_code == 404:
                logger.warning("Frame access validation failed: 404 Not Found")
                return {
                    "valid": False,
                    "title": "",
                    "message": "Frame or file not found"
                }

            elif response.status_code == 429:
                logger.warning("Frame access validation failed: 429 Rate limit exceeded")
                return {
                    "valid": False,
                    "title": "",
                    "message": "Rate limit exceeded, please try again later"
                }

            else:
                logger.warning(f"Frame access validation failed: HTTP {response.status_code}")
                return {
                    "valid": False,
                    "title": "",
                    "message": f"Figma API error: {response.status_code}"
                }

        except Timeout:
            logger.error(f"Frame access validation timeout after {FRAME_OPERATION_TIMEOUT} seconds")
            return {
                "valid": False,
                "title": "",
                "message": "Request timeout - Figma API did not respond in time"
            }

        except RequestException as e:
            logger.error(f"Frame access validation network error: {e}")
            return {
                "valid": False,
                "title": "",
                "message": "Network error connecting to Figma API"
            }

        except Exception as e:
            # Catch any unexpected errors to ensure we never raise
            logger.error(f"Frame access validation unexpected error: {e}", exc_info=True)
            return {
                "valid": False,
                "title": "",
                "message": "An unexpected error occurred during validation"
            }

    def get_frame_metadata(self, pat: str, frame_url: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve comprehensive frame metadata from Figma API.

        Fetches detailed information about a Figma frame including name, type,
        dimensions, parent file information, and other properties. This method
        provides richer metadata than validate_frame_access and is useful for
        displaying frame information in the UI or for advanced integration scenarios.

        Unlike validate_frame_access, this method returns the full metadata structure
        from Figma's API rather than a standardized validation response. Returns None
        if the frame is inaccessible or if any error occurs.

        :param pat: Figma Personal Access Token for authentication
        :type pat: str
        :param frame_url: Full Figma frame URL to retrieve metadata for
                         Format: https://www.figma.com/file/{file_key}/{file_name}?node-id={node_id}
                         or: https://www.figma.com/design/{file_key}/{file_name}?node-id={node_id}
        :type frame_url: str
        :return: Dictionary containing frame metadata from Figma API, or None if inaccessible
                 Typical structure includes:
                 - name (str): Frame/node name
                 - type (str): Node type (e.g., "FRAME", "COMPONENT", "INSTANCE")
                 - absoluteBoundingBox (dict): Frame dimensions and position
                 - children (list): Child nodes if applicable
                 Other fields vary based on Figma API response
        :rtype: Optional[Dict[str, Any]]

        Example Success Response:
            {
                "name": "Login Screen - Mobile",
                "type": "FRAME",
                "absoluteBoundingBox": {
                    "x": 0,
                    "y": 0,
                    "width": 375,
                    "height": 812
                },
                "backgroundColor": {
                    "r": 1,
                    "g": 1,
                    "b": 1,
                    "a": 1
                },
                "children": [...]
            }

        Returns None for Error Cases:
            - Invalid or expired PAT (401)
            - Access denied (403)
            - Frame not found (404)
            - Rate limit exceeded (429)
            - Network errors or timeouts
            - Malformed frame URL
            - JSON parsing errors

        Implementation Details:
            - Endpoint: GET https://api.figma.com/v1/files/{file_key}/nodes?ids={node_id}
            - Authentication: Bearer token in Authorization header
            - Timeout: 15 seconds
            - Response parsing: Extract nodes[node_id]['document']
            - Never raises exceptions - returns None on any error
            - All errors are logged for debugging

        Difference from validate_frame_access:
            - validate_frame_access returns standardized dict with valid/title/message
            - get_frame_metadata returns raw Figma API response or None
            - Use validate_frame_access for validation flows
            - Use get_frame_metadata when full frame details are needed

        Usage Example:
            >>> api_repo = FigmaAPIRepository()
            >>> frame_url = "https://www.figma.com/file/abc/design?node-id=1:2"
            >>> metadata = api_repo.get_frame_metadata("figd_AbC123...", frame_url)
            >>> if metadata:
            ...     print(f"Frame name: {metadata['name']}")
            ...     print(f"Frame type: {metadata['type']}")
            ...     print(f"Dimensions: {metadata['absoluteBoundingBox']['width']}x{metadata['absoluteBoundingBox']['height']}")
            ... else:
            ...     print("Could not retrieve frame metadata")
        """
        # Validate inputs
        if not pat or not isinstance(pat, str) or not pat.strip():
            logger.warning("get_frame_metadata called with empty or invalid PAT")
            return None

        if not frame_url or not isinstance(frame_url, str) or not frame_url.strip():
            logger.warning("get_frame_metadata called with empty or invalid frame_url")
            return None

        # Parse the Figma URL to extract file_key and node_id
        parsed_data = self._parse_figma_url(frame_url)
        if not parsed_data:
            logger.warning(f"Invalid Figma URL format for metadata retrieval: {frame_url}")
            return None

        file_key = parsed_data['file_key']
        node_id = parsed_data['node_id']

        try:
            # Construct Figma API endpoint for node retrieval
            url = f"{FIGMA_API_BASE}/files/{file_key}/nodes"
            headers = {
                "Authorization": f"Bearer {pat}",
                "Content-Type": "application/json"
            }
            params = {
                "ids": node_id
            }

            logger.debug(f"Retrieving frame metadata: file_key={file_key}, node_id={node_id}")

            response = requests.get(
                url,
                headers=headers,
                params=params,
                timeout=FRAME_OPERATION_TIMEOUT
            )

            # Handle successful response
            if response.status_code == 200:
                try:
                    data = response.json()

                    # Navigate to the frame/node data in the response
                    if 'nodes' in data and node_id in data['nodes']:
                        node_data = data['nodes'][node_id]

                        # Check if the node was successfully retrieved
                        if node_data is None:
                            logger.warning(f"Node {node_id} not found in file {file_key}")
                            return None

                        # Return the full document metadata
                        if 'document' in node_data:
                            logger.info(f"Frame metadata retrieved successfully for node {node_id}")
                            return node_data['document']
                        else:
                            logger.warning(f"Unexpected response structure: missing document key")
                            return None
                    else:
                        logger.warning(f"Node {node_id} not found in response")
                        return None

                except ValueError as e:
                    logger.error(f"Failed to parse Figma API JSON response: {e}")
                    return None

            # Log HTTP error responses and return None
            elif response.status_code == 401:
                logger.warning("Frame metadata retrieval failed: 401 Unauthorized")
                return None

            elif response.status_code == 403:
                logger.warning("Frame metadata retrieval failed: 403 Forbidden")
                return None

            elif response.status_code == 404:
                logger.warning("Frame metadata retrieval failed: 404 Not Found")
                return None

            elif response.status_code == 429:
                logger.warning("Frame metadata retrieval failed: 429 Rate limit exceeded")
                return None

            else:
                logger.warning(f"Frame metadata retrieval failed: HTTP {response.status_code}")
                return None

        except Timeout:
            logger.error(f"Frame metadata retrieval timeout after {FRAME_OPERATION_TIMEOUT} seconds")
            return None

        except RequestException as e:
            logger.error(f"Frame metadata retrieval network error: {e}")
            return None

        except Exception as e:
            # Catch any unexpected errors to ensure we never raise
            logger.error(f"Frame metadata retrieval unexpected error: {e}", exc_info=True)
            return None

    def _parse_figma_url(self, frame_url: str) -> Optional[Dict[str, str]]:
        """
        Parse Figma frame URL to extract file key and node ID.

        Supports both URL formats used by Figma:
            - https://www.figma.com/file/{file_key}/{file_name}?node-id={node_id}
            - https://www.figma.com/design/{file_key}/{file_name}?node-id={node_id}

        The node-id parameter can be URL-encoded (1%3A2) or plain (1:2).

        :param frame_url: Full Figma frame URL to parse
        :type frame_url: str
        :return: Dictionary with 'file_key' and 'node_id' keys, or None if parsing fails
        :rtype: Optional[Dict[str, str]]

        Example:
            >>> repo = FigmaAPIRepository()
            >>> result = repo._parse_figma_url(
            ...     "https://www.figma.com/file/abc123/MyDesign?node-id=1:2"
            ... )
            >>> print(result)
            {'file_key': 'abc123', 'node_id': '1:2'}

        Returns None for:
            - Non-Figma URLs
            - Missing file key
            - Missing node-id parameter
            - Malformed URLs
        """
        try:
            # Parse the URL to extract query parameters
            parsed = urlparse(frame_url)

            # Extract file_key using regex pattern
            match = FIGMA_URL_PATTERN.search(frame_url)
            if not match:
                logger.debug(f"URL does not match Figma pattern: {frame_url}")
                return None

            file_key = match.group(1)

            # Extract node_id from query parameters
            query_params = parse_qs(parsed.query)
            if 'node-id' not in query_params:
                logger.debug(f"URL missing node-id parameter: {frame_url}")
                return None

            # node-id parameter value (decode URL encoding if present)
            node_id = query_params['node-id'][0]

            # Validate that we have both required components
            if not file_key or not node_id:
                logger.debug(f"URL missing required components: file_key={file_key}, node_id={node_id}")
                return None

            return {
                'file_key': file_key,
                'node_id': node_id
            }

        except Exception as e:
            logger.error(f"Error parsing Figma URL: {e}")
            return None
